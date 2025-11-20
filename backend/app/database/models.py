from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .session import Base


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game_sessions = relationship("GameSession", back_populates="user", cascade="all, delete-orphan")


class GameSession(Base):
    """Game session model tracking a complete game."""
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_score = Column(Integer, default=0)
    rounds_completed = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="game_sessions")
    rounds = relationship("GameRound", back_populates="game_session", cascade="all, delete-orphan")


class GameRound(Base):
    """Individual round within a game session."""
    __tablename__ = "game_rounds"
    
    id = Column(Integer, primary_key=True, index=True)
    game_session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    
    # Photo information
    photo_id = Column(String(100), nullable=False)
    photo_url = Column(Text, nullable=False)
    actual_latitude = Column(Float, nullable=False)
    actual_longitude = Column(Float, nullable=False)
    
    # Guess information
    guess_latitude = Column(Float, nullable=True)
    guess_longitude = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)
    score = Column(Integer, default=0)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    game_session = relationship("GameSession", back_populates="rounds")
