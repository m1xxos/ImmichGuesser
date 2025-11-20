from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GuessRequest(BaseModel):
    """Request for submitting a guess."""
    latitude: float
    longitude: float


class GuessResponse(BaseModel):
    """Response after submitting a guess."""
    distance_km: float
    score: int
    actual_latitude: float
    actual_longitude: float
    round_completed: bool
    game_completed: bool
    immich_url: Optional[str] = None


class PhotoResponse(BaseModel):
    """Response with photo for guessing (GPS stripped)."""
    photo_id: str
    photo_url: str
    round_number: int


class GameSessionCreate(BaseModel):
    """Request to create a new game session."""
    pass


class GameSessionResponse(BaseModel):
    """Response with game session details."""
    id: int
    total_score: int
    rounds_completed: int
    is_completed: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RoundResponse(BaseModel):
    """Response with round details."""
    round_number: int
    photo_id: str
    distance_km: Optional[float] = None
    score: int
    actual_latitude: Optional[float] = None
    actual_longitude: Optional[float] = None
    guess_latitude: Optional[float] = None
    guess_longitude: Optional[float] = None
    
    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    username: str
    total_score: int
    completed_at: datetime
    
    class Config:
        from_attributes = True


class LeaderboardResponse(BaseModel):
    """Response with leaderboard."""
    entries: List[LeaderboardEntry]
