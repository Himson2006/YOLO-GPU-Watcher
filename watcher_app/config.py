import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # must be set in env: postgres://user:pass@HOST:5432/dbname
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # where incoming videos arrive (export WATCH_FOLDER before running)
    WATCH_FOLDER = os.environ.get(
        "WATCH_FOLDER",
        os.path.join(basedir, "..", "incoming")
    )

    # where to write per-video JSON
    JSON_FOLDER = os.environ.get(
        "JSON_FOLDER",
        os.path.join(basedir, "..", "detections")
    )

    # path to YOLO weights (export YOLO_MODEL_PATH before running)
    YOLO_MODEL_PATH = os.environ.get(
        "YOLO_MODEL_PATH",
        os.path.join(basedir, "..", "yolo_weights", "best.pt")
    )
