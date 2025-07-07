from . import db
from sqlalchemy.dialects.postgresql import JSONB

class Video(db.Model):
    __tablename__ = "videos"
    id          = db.Column(db.Integer, primary_key=True)
    filename    = db.Column(db.String(256), nullable=False, unique=True)
    detection   = db.relationship(
        "Detection", backref="video", uselist=False, cascade="all, delete"
    )

class Detection(db.Model):
    __tablename__ = "detections"
    id                  = db.Column(db.Integer, primary_key=True)
    video_id            = db.Column(
        db.Integer, db.ForeignKey("videos.id"), nullable=False, unique=True
    )
    detection_json      = db.Column(JSONB, nullable=False)
    classes_detected    = db.Column(db.String(256), nullable=True)
    max_count_per_frame = db.Column(JSONB, nullable=True)