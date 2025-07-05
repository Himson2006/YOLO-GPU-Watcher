# models.py
from sqlalchemy import (
    Column, Integer, String, ForeignKey, create_engine
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import Config

Base = declarative_base()
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)

class Video(Base):
    __tablename__ = "videos"
    id       = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, nullable=False)
    detections = relationship(
        "Detection", back_populates="video",
        cascade="all, delete-orphan"
    )

class Detection(Base):
    __tablename__ = "detections"
    id                  = Column(Integer, primary_key=True, index=True)
    video_id            = Column(Integer, ForeignKey("videos.id"), nullable=False)
    detection_json      = Column(JSONB, nullable=False)
    classes_detected    = Column(String, nullable=True)
    max_count_per_frame = Column(JSONB, nullable=True)

    video = relationship("Video", back_populates="detections")

# create tables if they don’t exist
Base.metadata.create_all(bind=engine)
