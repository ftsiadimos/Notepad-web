from app import create_app, db
import os

app = create_app()

if __name__ == '__main__':
    # Get port from environment variables (check both FLASK_RUN_PORT and PORT)
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5223)))
    # Get host from environment (default to 0.0.0.0 for Docker compatibility)
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    try:
        with app.app_context():
            # Initialize database
            db.create_all()
            print("Database initialized successfully")
        
        # Run the application
        app.run(host=host, port=port, debug=debug)
    except Exception as e:
        print(f"Error starting application: {e}")
        exit(1)
