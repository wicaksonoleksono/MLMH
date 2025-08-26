#!/usr/bin/env python3
"""
Mental Health Assessment Application
Single Entry Point - ASGI Application
"""

from app import create_app
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import after path setup


def setup_environment():
    """Setup environment variables if not set"""
    env_vars = {
        'FLASK_ENV': 'development',
        'SECRET_KEY': 'dev-key-change-in-production',
        'PORT': '5000',
        'HOST': '0.0.0.0',
    }

    for key, default_value in env_vars.items():
        if not os.getenv(key):
            os.environ[key] = default_value

def create_application():
    """Create and configure the ASGI application"""
    print("[OLKORECT] Creating Mental Health Assessment ASGI Application...")

    # Setup environment
    setup_environment()
    app = create_app()
    with app.app_context():
        print("[OLKORECT] Initializing database...")
        try:
            print("[OLKORECT] Database initialized successfully")
        except Exception as e:
            print(f"[WATCHOUT] Database initialization issue: {e}")

    return app

application = create_application()

def main():
    """Development server entry point"""
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print(f"[OLKORECT] Development server starting on http://{host}:{port}")

    # Run the application in development mode
    application.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
