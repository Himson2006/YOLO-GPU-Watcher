# config.py
import os

class Config:
    # point this at your Postgres on VM 1
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://yolo_user:yolo_pass@V20.14.93.39:5432/yolo_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # where watcher looks for new videos
    WATCH_FOLDER = os.environ.get(
        "WATCH_FOLDER",
        os.path.expanduser("~/incoming")
    )

    # where your best.pt lives
    YOLO_MODEL_PATH = os.environ.get(
        "YOLO_MODEL_PATH",
        os.path.join(os.path.dirname(__file__), "yolo_weights", "best.pt")
    )
