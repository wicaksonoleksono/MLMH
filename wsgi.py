#!/usr/bin/env python3
"""
WSGI entry point for MLMH Flask application
Production deployment: Gunicorn/uWSGI will import 'application' from this file
Development: Can run directly with `python wsgi.py`
"""

import os
import sys

# Add the project directory to Python path for production deployment
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import Flask app
from app import create_app
from app.config import Config

# Create the Flask application instance
flask_app = create_app()

# WSGI application object (this is what production servers look for)
application = flask_app

# For development server
if __name__ == "__main__":
    flask_app.run(
        host='127.0.0.1',
        port=Config.FLASK_PORT,
        debug=Config.DEBUG
    )