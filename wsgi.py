#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dashboard.app import app

# This is what Gunicorn will look for
server = app.server

if __name__ == "__main__":
    app.run_server(debug=False)