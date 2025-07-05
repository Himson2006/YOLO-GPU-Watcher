from sqlalchemy import (
    Column, Integer, String, JSON, ForeignKey, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Video(Base):
    __tablename__ = "videos"
    id       = Column(Integer, primary_key=True)
    filename = Column(String, unique=True, nullable=False, index=True)
    detections = relationship("Detection", back_populates="video", cascade="all, delete")

class Detection(Base):
    __tablename__ = "detections"
    id                  = Column(Integer, primary_key=True)
    video_id            = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    detection_json      = Column(JSON, nullable=False)
    classes_detected    = Column(String)
    max_count_per_frame = Column(JSON)
    video = relationship("Video", back_populates="detections")
