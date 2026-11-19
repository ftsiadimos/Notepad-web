from app import create_app, db
from flask_migrate import upgrade, stamp
from sqlalchemy import text
import os

app = create_app()


TARGET_REVISION = "initial_schema"


def _get_alembic_revision():
    """Return current alembic version from DB, or None when unavailable."""
    result = db.session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    return result


def _set_alembic_revision(revision):
    """Force alembic_version to a known good revision."""
    db.session.execute(text("DELETE FROM alembic_version"))
    db.session.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
        {"revision": revision},
    )
    db.session.commit()


def _ensure_migration_state(existing_tables):
    """Normalize migration state for Docker volumes with stale alembic revision IDs."""
    has_business_tables = any(table in existing_tables for table in ("note", "app_setting", "category"))
    has_alembic_table = "alembic_version" in existing_tables

    if not has_business_tables:
        return

    if not has_alembic_table:
        print("Tables exist without alembic_version. Creating migration state...")
        db.session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        _set_alembic_revision(TARGET_REVISION)
        print(f"Migration state set to {TARGET_REVISION}")
        return

    current_revision = _get_alembic_revision()
    if current_revision != TARGET_REVISION:
        print(
            f"Found stale migration revision '{current_revision}'. "
            f"Resetting migration state to '{TARGET_REVISION}'..."
        )
        _set_alembic_revision(TARGET_REVISION)
        print("Migration state corrected")


def _run_upgrade_with_recovery():
    """Run Flask-Migrate upgrade and convert SystemExit into recoverable error."""
    try:
        upgrade()
        print("Database migrated successfully")
    except SystemExit as exc:
        # Flask-Migrate can terminate the process on migration command errors.
        raise RuntimeError(f"Migration command aborted: {exc}") from exc


def init_db():
    """Initialize database by running migrations."""
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()

            _ensure_migration_state(existing_tables)
            _run_upgrade_with_recovery()

        except RuntimeError as e:
            error_msg = str(e).lower()

            if 'already exists' in error_msg or 'table' in error_msg:
                print("Tables already exist. Stamping migration state...")
                try:
                    stamp(revision=TARGET_REVISION)
                    print("Database stamped successfully")
                except (RuntimeError, SystemExit, Exception) as stamp_error:
                    print(f"Warning: Could not stamp database: {stamp_error}")
                    print("Continuing anyway...")

            elif 'locate revision' in error_msg or 'can\'t locate' in error_msg:
                print(f"Migration revision not found: {e}")
                print("Attempting recovery...")
                try:
                    db.create_all()
                    _set_alembic_revision(TARGET_REVISION)
                    print("Database recovered successfully")
                except Exception as recovery_error:
                    print(f"Error recovering database: {recovery_error}")
                    print("Continuing with basic setup...")
            else:
                print(f"Database migration error: {e}")
                try:
                    print("Attempting fallback: creating all tables...")
                    db.create_all()
                    if "alembic_version" not in db.inspect(db.engine).get_table_names():
                        db.session.execute(
                            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
                        )
                        db.session.commit()
                    _set_alembic_revision(TARGET_REVISION)
                    print("Tables created successfully")
                except Exception as fallback_error:
                    print(f"Error creating tables: {fallback_error}")
                    exit(1)
        except Exception as e:
            print(f"Unexpected database migration error: {e}")
            try:
                db.create_all()
                if "alembic_version" not in db.inspect(db.engine).get_table_names():
                    db.session.execute(
                        text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
                    )
                    db.session.commit()
                _set_alembic_revision(TARGET_REVISION)
                print("Fallback database initialization completed")
            except Exception as fallback_error:
                print(f"Error creating tables during fallback: {fallback_error}")
                exit(1)

if __name__ == '__main__':
    init_db()
    
    # Run the application
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5223)))
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)
