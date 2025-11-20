from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List

from ..database.session import get_db
from ..database.models import User, GameSession, GameRound
from ..models.game import (
    GameSessionCreate, GameSessionResponse, PhotoResponse,
    GuessRequest, GuessResponse, LeaderboardResponse, LeaderboardEntry,
    RoundResponse
)
from ..dependencies import get_current_user
from ..services.immich import ImmichClient
from ..services.scoring import haversine_distance, calculate_score
from ..config import get_settings

router = APIRouter(prefix="/game", tags=["Game"])
settings = get_settings()

# Initialize Immich client
immich_client = ImmichClient(settings.IMMICH_API_URL, settings.IMMICH_API_KEY)


@router.post("/start", response_model=GameSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_game(
    game_data: GameSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a new game session."""
    
    # Check if user has an incomplete game
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    existing_game = result.scalar_one_or_none()
    
    if existing_game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active game. Complete it or delete it first."
        )
    
    # Fetch random photos with GPS from Immich
    try:
        photos = await immich_client.get_random_photos_with_gps(settings.ROUNDS_PER_GAME)
    except HTTPException as e:
        raise e
    
    # Create new game session
    new_game = GameSession(
        user_id=current_user.id,
        total_score=0,
        rounds_completed=0,
        is_completed=False
    )
    db.add(new_game)
    await db.flush()
    
    # Create rounds for each photo
    for i, photo in enumerate(photos, 1):
        round_data = GameRound(
            game_session_id=new_game.id,
            round_number=i,
            photo_id=photo["id"],
            photo_url=photo["thumbnailUrl"],
            immich_url=photo.get("immichUrl"),
            actual_latitude=photo["latitude"],
            actual_longitude=photo["longitude"]
        )
        db.add(round_data)
    
    await db.commit()
    await db.refresh(new_game)
    
    return new_game


@router.get("/current", response_model=GameSessionResponse)
async def get_current_game(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current game session (active or just completed)."""
    
    # First try to get active game
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    game = result.scalar_one_or_none()
    
    # If no active game, try to get the most recently completed one
    if not game:
        result = await db.execute(
            select(GameSession).where(
                GameSession.user_id == current_user.id
            ).order_by(desc(GameSession.completed_at)).limit(1)
        )
        game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game found. Start a new game."
        )
    
    return game


@router.get("/photo", response_model=PhotoResponse)
async def get_current_photo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current photo to guess (without GPS coordinates)."""
    
    # Get current game
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game found. Start a new game."
        )
    
    # Get current round (next incomplete round)
    result = await db.execute(
        select(GameRound).where(
            GameRound.game_session_id == game.id,
            GameRound.completed_at == None
        ).order_by(GameRound.round_number).limit(1)
    )
    current_round = result.scalar_one_or_none()
    
    if not current_round:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All rounds completed. Game is finished."
        )
    
    # Return photo WITHOUT GPS coordinates
    return PhotoResponse(
        photo_id=current_round.photo_id,
        photo_url=f"/game/photo/{current_round.photo_id}/preview",
        round_number=current_round.round_number
    )


@router.post("/guess", response_model=GuessResponse)
async def submit_guess(
    guess: GuessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit a guess for the current round."""
    
    # Get current game
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game found."
        )
    
    # Get current round
    result = await db.execute(
        select(GameRound).where(
            GameRound.game_session_id == game.id,
            GameRound.completed_at == None
        ).order_by(GameRound.round_number).limit(1)
    )
    current_round = result.scalar_one_or_none()
    
    if not current_round:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active round found."
        )
    
    # Calculate distance and score
    distance = haversine_distance(
        guess.latitude, guess.longitude,
        current_round.actual_latitude, current_round.actual_longitude
    )
    score = calculate_score(distance, settings.MAX_POINTS)
    
    # Update round
    current_round.guess_latitude = guess.latitude
    current_round.guess_longitude = guess.longitude
    current_round.distance_km = distance
    current_round.score = score
    current_round.completed_at = datetime.utcnow()
    
    # Update game session
    game.total_score += score
    game.rounds_completed += 1
    
    # Check if game is completed
    game_completed = game.rounds_completed >= settings.ROUNDS_PER_GAME
    if game_completed:
        game.is_completed = True
        game.completed_at = datetime.utcnow()
    
    await db.commit()
    
    return GuessResponse(
        distance_km=distance,
        score=score,
        actual_latitude=current_round.actual_latitude,
        actual_longitude=current_round.actual_longitude,
        round_completed=True,
        game_completed=game_completed,
        immich_url=current_round.immich_url
    )


@router.get("/rounds", response_model=List[RoundResponse])
async def get_game_rounds(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all rounds for the current game."""
    
    # Get current game (active or most recently completed)
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    game = result.scalar_one_or_none()
    
    # If no active game, get most recently completed
    if not game:
        result = await db.execute(
            select(GameSession).where(
                GameSession.user_id == current_user.id
            ).order_by(desc(GameSession.completed_at)).limit(1)
        )
        game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game found."
        )
    
    # Get all rounds
    result = await db.execute(
        select(GameRound).where(
            GameRound.game_session_id == game.id
        ).order_by(GameRound.round_number)
    )
    rounds = result.scalars().all()
    
    return rounds


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get the top scores leaderboard."""
    
    # Get top completed games
    result = await db.execute(
        select(GameSession, User).join(User).where(
            GameSession.is_completed == True
        ).order_by(desc(GameSession.total_score)).limit(limit)
    )
    
    entries = []
    for game, user in result:
        entries.append(LeaderboardEntry(
            username=user.username,
            total_score=game.total_score,
            completed_at=game.completed_at
        ))
    
    return LeaderboardResponse(entries=entries)


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_game(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete the current active game."""
    
    result = await db.execute(
        select(GameSession).where(
            GameSession.user_id == current_user.id,
            GameSession.is_completed == False
        )
    )
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active game found."
        )
    
    await db.delete(game)
    await db.commit()
    
    return None


@router.get("/photo/{asset_id}/{quality}")
async def get_photo_proxy(
    asset_id: str,
    quality: str,
    current_user: User = Depends(get_current_user)
):
    """Proxy photo requests to Immich with API key."""
    try:
        if quality == "preview":
            image_bytes = await immich_client.get_asset_preview(asset_id)
        elif quality == "original":
            image_bytes = await immich_client.get_asset_original(asset_id)
        else:
            image_bytes = await immich_client.get_asset_thumbnail(asset_id)
        return Response(content=image_bytes, media_type="image/jpeg")
    except HTTPException as e:
        raise e
