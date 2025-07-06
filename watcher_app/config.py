import os
from dotenv import load_dotenv

# Load from .env into os.environ
load_dotenv(override=True)

class Config:
    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Watch folder
    WATCH_FOLDER = os.environ["WATCH_FOLDER"]

    # YOLO model
    YOLO_MODEL_PATH = os.environ["YOLO_MODEL_PATH"]
