from app import create_app, db
from flask_migrate import upgrade, stamp, current
from flask import Flask
import os

app = create_app()

def init_db():
    """Initialize database by running migrations."""
    with app.app_context():
        try:
            # Check if database is completely new (no tables at all)
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # If we have tables but no alembic_version, stamp it
            if existing_tables and 'alembic_version' not in existing_tables:
                print("Database tables exist but no migration history. Stamping as initial_schema...")
                try:
                    stamp(revision='initial_schema')
                    print("Database stamped successfully")
                    return
                except Exception as e:
                    print(f"Could not stamp database: {e}")
            
            # Try normal migration
            upgrade()
            print("Database migrated successfully")
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # If tables already exist, just stamp and continue
            if 'already exists' in error_msg or 'table' in error_msg:
                print(f"Tables already exist, stamping migration state...")
                try:
                    with app.app_context():
                        stamp(revision='initial_schema')
                        print("Database stamped successfully")
                except Exception as stamp_error:
                    print(f"Warning: Could not stamp database: {stamp_error}")
                    print("Continuing anyway...")
            
            # If the error is about a missing revision, try to stamp the current state
            elif 'locate revision' in error_msg or 'can\'t locate' in error_msg:
                print(f"Migration revision not found: {e}")
                print("Attempting to recovery...")
                try:
                    db.create_all()
                    stamp(revision='initial_schema')
                    print("Database recovered successfully")
                except Exception as recovery_error:
                    print(f"Error recovering database: {recovery_error}")
                    print("Continuing with basic setup...")
            else:
                print(f"Database migration error: {e}")
                # Try fallback
                try:
                    print("Attempting fallback: creating all tables...")
                    db.create_all()
                    print("Tables created successfully")
                except Exception as fallback_error:
                    print(f"Error creating tables: {fallback_error}")
                    exit(1)

if __name__ == '__main__':
    init_db()
    
    # Run the application
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5223)))
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)
