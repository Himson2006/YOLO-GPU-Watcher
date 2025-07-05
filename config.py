import os

class Config:
    # e.g. "postgresql://yolo_user:yolo_pass@VM1_IP:5432/yolo_db"
    DATABASE_URL   = os.environ.get("DATABASE_URL")
    # where new videos land
    WATCH_FOLDER   = os.environ.get("WATCH_FOLDER", os.path.expanduser("~/YOLO-GPU-Watcher/incoming"))
    # where your GPU-optimized weights live
    YOLO_MODEL_PATH= os.environ.get("YOLO_MODEL_PATH", os.path.expanduser("~/YOLO-GPU-Watcher/yolo_weights/best.pt"))
