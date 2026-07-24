"""WSGI entry point for the Nexarch Flask API."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
