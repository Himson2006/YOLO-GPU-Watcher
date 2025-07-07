# manage.py
import os
from dotenv import load_dotenv
from watcher_app import create_app, db

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = create_app()
with app.app_context():
    db.create_all()
    print("✅ Tables created")
