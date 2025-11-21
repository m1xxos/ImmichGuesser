from typing import List, Optional, Dict, Any
from datetime import datetime, date
import httpx
from fastapi import HTTPException, status
import random


class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Accept": "application/json"
        }
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in kilometers using haversine formula."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth radius in km
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    async def get_random_photos_with_gps(
        self, 
        count: int = 5,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch random photos from Immich that have GPS coordinates.
        Photos are selected from different days and at least 1km apart from each other.
        
        Args:
            count: Number of photos to fetch
            start_date: Optional filter - photos taken after this date
            end_date: Optional filter - photos taken before this date
            
        Returns:
            List of photo dictionaries with GPS data
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Collect all photos with GPS from multiple pages
                all_photos = []
                max_pages = 20  # Scan up to 20 pages
                
                for page in range(1, max_pages + 1):
                    search_params = {
                        "isNotInAlbum": False,
                        "withExif": True,
                        "size": 100,
                        "page": page
                    }
                    
                    # Add date filters if provided
                    if start_date:
                        search_params["takenAfter"] = start_date.isoformat() + "T00:00:00.000Z"
                    if end_date:
                        search_params["takenBefore"] = end_date.isoformat() + "T23:59:59.999Z"
                    
                    response = await client.post(
                        f"{self.api_url}/search/metadata",
                        headers=self.headers,
                        json=search_params
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Get assets from response
                    assets = result.get("assets", {}).get("items", []) if isinstance(result.get("assets"), dict) else result.get("assets", [])
                    
                    if not assets:
                        break  # No more photos
                    
                    # Filter assets that have GPS coordinates
                    for asset in assets:
                        exif_info = asset.get("exifInfo", {})
                        if exif_info:
                            lat = exif_info.get("latitude")
                            lon = exif_info.get("longitude")
                            date_taken_str = exif_info.get("dateTimeOriginal")
                            
                            # Check if coordinates exist and are not None/0
                            if lat and lon and lat != 0 and lon != 0 and date_taken_str:
                                asset_id = asset.get("id")
                                all_photos.append({
                                    "id": asset_id,
                                    "thumbnailUrl": f"/game/photo/{asset_id}/preview",
                                    "originalUrl": f"{self.api_url}/assets/{asset_id}/original",
                                    "immichUrl": f"{self.api_url.replace('/api', '')}/photos/{asset_id}",
                                    "latitude": lat,
                                    "longitude": lon,
                                    "city": exif_info.get("city"),
                                    "state": exif_info.get("state"),
                                    "country": exif_info.get("country"),
                                    "dateTaken": date_taken_str,
                                })
                
                if len(all_photos) < count:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Not enough photos with GPS coordinates found. Found {len(all_photos)}, need {count}. Make sure your photos have GPS metadata in Immich and EXIF extraction is enabled."
                    )
                
                # Group photos by day
                photos_by_day = {}
                for photo in all_photos:
                    try:
                        # Parse date and extract just the day
                        date_obj = datetime.fromisoformat(photo["dateTaken"].replace("Z", "+00:00"))
                        day_key = date_obj.date().isoformat()
                        
                        if day_key not in photos_by_day:
                            photos_by_day[day_key] = []
                        photos_by_day[day_key].append(photo)
                    except (ValueError, AttributeError):
                        continue
                
                if len(photos_by_day) < count:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Not enough different days with photos. Found {len(photos_by_day)} days, need {count}. Try widening your date range."
                    )
                
                # Select photos from different days with minimum 1km distance
                selected_photos = []
                available_days = list(photos_by_day.keys())
                random.shuffle(available_days)
                
                max_attempts = len(available_days) * 10  # Prevent infinite loop
                attempts = 0
                
                for day in available_days:
                    if len(selected_photos) >= count:
                        break
                    
                    attempts += 1
                    if attempts > max_attempts:
                        break
                    
                    # Shuffle photos from this day
                    day_photos = photos_by_day[day]
                    random.shuffle(day_photos)
                    
                    # Try to find a photo that is at least 1km away from all selected photos
                    for photo in day_photos:
                        if len(selected_photos) >= count:
                            break
                        
                        # Check distance from all already selected photos
                        too_close = False
                        for selected in selected_photos:
                            distance = self._calculate_distance(
                                photo["latitude"], photo["longitude"],
                                selected["latitude"], selected["longitude"]
                            )
                            if distance < 1.0:  # Less than 1km
                                too_close = True
                                break
                        
                        if not too_close:
                            selected_photos.append(photo)
                            break
                
                if len(selected_photos) < count:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Could not find {count} photos from different days that are at least 1km apart. Found {len(selected_photos)}. Try widening your date range or check your photo library."
                    )
                
                return selected_photos
                
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Error connecting to Immich: {str(e)}"
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Cannot reach Immich server: {str(e)}"
                )
    
    async def get_asset_thumbnail(self, asset_id: str) -> bytes:
        """
        Get thumbnail image for an asset.
        
        Args:
            asset_id: The asset ID
            
        Returns:
            Image bytes
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/assets/{asset_id}/thumbnail",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Error fetching thumbnail: {str(e)}"
                )
    
    async def get_asset_preview(self, asset_id: str) -> bytes:
        """
        Get preview (high quality) image for an asset.
        
        Args:
            asset_id: The asset ID
            
        Returns:
            Image bytes
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/assets/{asset_id}/thumbnail?size=preview",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Error fetching preview image: {str(e)}"
                )
    
    async def get_asset_original(self, asset_id: str) -> bytes:
        """
        Get original quality image for an asset.
        
        Args:
            asset_id: The asset ID
            
        Returns:
            Image bytes
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(
                    f"{self.api_url}/assets/{asset_id}/original",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Error fetching original image: {str(e)}"
                )
