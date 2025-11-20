from math import radians, sin, cos, sqrt, atan2
from typing import Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Coordinates of the first point (degrees)
        lat2, lon2: Coordinates of the second point (degrees)
        
    Returns:
        Distance in kilometers
    """
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert coordinates to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance


def calculate_score(distance_km: float, max_points: int = 5000) -> int:
    """
    Calculate score based on distance from actual location.
    
    Scoring system (more strict):
    - Perfect guess (< 0.1km): max_points
    - < 1km: 4000 points
    - < 10km: 3000-2000 points
    - < 50km: 2000-1000 points
    - < 100km: 1000-500 points
    - < 500km: 500-100 points
    - < 1000km: 100-50 points
    - > 1000km: 50-0 points
    
    Args:
        distance_km: Distance in kilometers
        max_points: Maximum possible points
        
    Returns:
        Score (0 to max_points)
    """
    if distance_km < 0.1:  # < 100m - Perfect!
        return max_points
    elif distance_km < 1:  # < 1km - Excellent
        return 4000
    elif distance_km < 10:  # < 10km - Very good
        ratio = (distance_km - 1) / 9
        return int(3000 - ratio * 1000)
    elif distance_km < 50:  # < 50km - Good
        ratio = (distance_km - 10) / 40
        return int(2000 - ratio * 1000)
    elif distance_km < 100:  # < 100km - Okay
        ratio = (distance_km - 50) / 50
        return int(1000 - ratio * 500)
    elif distance_km < 500:  # < 500km - Not great
        ratio = (distance_km - 100) / 400
        return int(500 - ratio * 400)
    elif distance_km < 1000:  # < 1000km - Poor
        ratio = (distance_km - 500) / 500
        return int(100 - ratio * 50)
    else:  # > 1000km - Very poor
        return max(0, int(50 * (1 - min(distance_km / 10000, 1))))
