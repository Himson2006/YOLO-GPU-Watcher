import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # must be set in env
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # where to watch (env override or default to incoming/)
    WATCH_FOLDER = os.environ.get(
        "WATCH_FOLDER",
        os.path.join(basedir, os.pardir, "incoming")
    )

    # where your best.pt lives
    YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH")
