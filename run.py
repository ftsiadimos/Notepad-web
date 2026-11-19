from pathlib import Path
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from app import create_app, db
from models import Note, AppSetting, Category

app = create_app()


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _get_script_directory():
    config = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config)


def _get_migration_head():
    script = _get_script_directory()
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(
            f"Expected one database migration head, found {len(heads)}: {heads}"
        )
    return heads[0]


def _get_alembic_revision():
    if "alembic_version" not in inspect(db.engine).get_table_names():
        return None

    revisions = db.session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalars().all()
    if len(revisions) > 1:
        raise RuntimeError(f"Multiple database revisions found: {revisions}")
    return revisions[0] if revisions else None


def _is_known_revision(revision):
    if revision is None:
        return False
    try:
        return _get_script_directory().get_revision(revision) is not None
    except CommandError:
        return False


def _quote_identifier(identifier):
    return db.engine.dialect.identifier_preparer.quote(identifier)


def _reconcile_current_schema():
    """Bring databases with removed/unknown revision IDs to the current schema."""
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    model_tables = [
        db.metadata.tables[name]
        for name in (
            Note.__tablename__,
            AppSetting.__tablename__,
            Category.__tablename__,
        )
    ]
    db.metadata.create_all(
        bind=db.engine,
        tables=[table for table in model_tables if table.name not in existing_tables],
    )

    inspector.clear_cache()
    for table in model_tables:
        existing_columns = {
            column["name"] for column in inspect(db.engine).get_columns(table.name)
        }
        missing_columns = [
            column for column in table.columns if column.name not in existing_columns
        ]

        for column in missing_columns:
            if not column.nullable and column.server_default is None:
                raise RuntimeError(
                    f"Cannot safely add required column {table.name}.{column.name} "
                    "to an existing database without a server default"
                )

            column_sql = str(
                CreateColumn(column).compile(dialect=db.engine.dialect)
            )
            db.session.execute(
                text(
                    f"ALTER TABLE {_quote_identifier(table.name)} "
                    f"ADD COLUMN {column_sql}"
                )
            )
            db.session.commit()

        inspector = inspect(db.engine)
        existing_indexes = {
            index["name"] for index in inspector.get_indexes(table.name)
        }
        for index in table.indexes:
            if index.name not in existing_indexes:
                index.create(bind=db.engine)

        final_columns = {
            column["name"] for column in inspect(db.engine).get_columns(table.name)
        }
        missing = {column.name for column in table.columns} - final_columns
        if missing:
            raise RuntimeError(
                f"Schema reconciliation failed for {table.name}; missing: "
                f"{sorted(missing)}"
            )


def init_db():
    """Bring the database to the sole current migration head."""
    with app.app_context():
        current_revision = _get_alembic_revision()
        head_revision = _get_migration_head()
        revision_is_known = _is_known_revision(current_revision)

        if revision_is_known:
            upgrade(revision=head_revision)
        else:
            print(
                f"Database revision '{current_revision}' is not present in this "
                f"image. Reconciling the existing schema with {head_revision}..."
            )

        _reconcile_current_schema()
        if not revision_is_known:
            stamp(revision=head_revision, purge=True)

        final_revision = _get_alembic_revision()
        if final_revision != head_revision:
            raise RuntimeError(
                f"Database migration did not reach {head_revision}; "
                f"revision is {final_revision}"
            )
        print(f"Database migrated successfully to {final_revision}")


if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("FLASK_RUN_PORT", os.environ.get("PORT", 5223)))
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    app.run(host=host, port=port, debug=debug)
