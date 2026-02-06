"""WSGI entry point for Gunicorn."""
from dam.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
