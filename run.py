from app import create_app, db
from flask_migrate import upgrade
from flask import Flask
import os

app = create_app()

def init_db():
    """Initialize database by running migrations."""
    try:
        with app.app_context():
            upgrade()
        print("Database migrated successfully")
    except Exception as e:
        print(f"Database migration error: {e}")
        exit(1)

if __name__ == '__main__':
    init_db()
    
    # Run the application
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5223)))
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)
