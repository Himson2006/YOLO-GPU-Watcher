from . import db
from sqlalchemy.dialects.postgresql import JSONB

class Video(db.Model):
    __tablename__ = "video"

    id       = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, unique=True, nullable=False)

    # one-to-one
    detection = db.relationship(
        "Detection",
        back_populates="video",
        cascade="all, delete",
        uselist=False,
    )

class Detection(db.Model):
    __tablename__ = "detection"

    id                  = db.Column(db.Integer, primary_key=True)
    video_id            = db.Column(
        db.Integer,
        db.ForeignKey("video.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    detection_json      = db.Column(JSONB, nullable=False)
    classes_detected    = db.Column(db.String, nullable=True)
    max_count_per_frame = db.Column(JSONB, nullable=True)

    video = db.relationship("Video", back_populates="detection")
