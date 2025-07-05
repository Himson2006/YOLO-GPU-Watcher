import os

class Config:
    # must be set in your environment:
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # must point at your “incoming” folder
    WATCH_FOLDER      = os.environ["WATCH_FOLDER"]
    # must point at best.pt on your GPU VM
    YOLO_MODEL_PATH   = os.environ["YOLO_MODEL_PATH"]
