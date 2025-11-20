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
    
    Scoring system:
    - Perfect guess (< 1km): max_points
    - 1-10km: exponential decay
    - 10-100km: linear decay
    - > 100km: minimal points
    
    Args:
        distance_km: Distance in kilometers
        max_points: Maximum possible points
        
    Returns:
        Score (0 to max_points)
    """
    if distance_km < 0.001:  # Almost perfect
        return max_points
    elif distance_km < 1:  # < 1km
        return int(max_points * 0.95)
    elif distance_km < 10:  # 1-10km
        return int(max_points * (1 - (distance_km / 10) * 0.5))
    elif distance_km < 100:  # 10-100km
        return int(max_points * 0.5 * (1 - (distance_km - 10) / 90))
    elif distance_km < 1000:  # 100-1000km
        return int(max_points * 0.1 * (1 - (distance_km - 100) / 900))
    else:  # > 1000km
        return max(10, int(max_points * 0.01))
