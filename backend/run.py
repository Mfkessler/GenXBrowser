#!/usr/bin/env python3
"""
H5AD Backend Entry Point
========================
Simple entry point for Gunicorn or direct execution.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Development mode only
    import os
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
