"""
SQLAlchemy models for the bag counting Edge system.
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.config import settings

# Ensure DB directory exists
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{settings.DB_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class BagClass(str, PyEnum):
    EMPTY = "empty"
    CLASS_25KG = "25kg"
    CLASS_50KG = "50kg"


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    operator_name = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True)

    wagons = relationship("Wagon", back_populates="shift", cascade="all, delete-orphan")
    bags = relationship("BagEvent", back_populates="shift")


class Wagon(Base):
    __tablename__ = "wagons"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    wagon_number = Column(String(32), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    target_weight_kg = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)

    shift = relationship("Shift", back_populates="wagons")
    bags = relationship("BagEvent", back_populates="wagon", cascade="all, delete-orphan")


class BagEvent(Base):
    __tablename__ = "bag_events"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    wagon_id = Column(Integer, ForeignKey("wagons.id"), nullable=False)

    # Tracking
    track_id = Column(Integer, nullable=False, index=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    counted_at = Column(DateTime, nullable=True)

    # Classification
    bag_class = Column(Enum(BagClass), nullable=False)
    estimated_volume_liters = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)

    # Geometry at moment of counting
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)
    bbox_x2 = Column(Float, nullable=True)
    bbox_y2 = Column(Float, nullable=True)

    # Video evidence
    clip_path = Column(Text, nullable=True)
    clip_start_offset_sec = Column(Float, nullable=True)
    clip_end_offset_sec = Column(Float, nullable=True)

    shift = relationship("Shift", back_populates="bags")
    wagon = relationship("Wagon", back_populates="bags")


def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
