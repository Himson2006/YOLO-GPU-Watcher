from watcher_app import db
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, backref

class Video(db.Model):
    __tablename__ = "videos"
    id       = Column(Integer, primary_key=True)
    filename = Column(String, unique=True, nullable=False)

class Detection(db.Model):
    __tablename__ = "detections"
    id                  = Column(Integer, primary_key=True)
    video_id            = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    detection_json      = Column(JSONB, nullable=False)
    classes_detected    = Column(String)
    max_count_per_frame = Column(JSONB)

    video = relationship("Video", backref=backref("detection", cascade="all, delete"))
