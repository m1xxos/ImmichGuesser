from typing import List, Optional, Dict, Any
import httpx
from fastapi import HTTPException, status


class ImmichClient:
    """Client for interacting with Immich API."""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Accept": "application/json"
        }
    
    async def get_random_photos_with_gps(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch random photos from Immich that have GPS coordinates.
        
        Args:
            count: Number of photos to fetch
            
        Returns:
            List of photo dictionaries with GPS data
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Request random assets from Immich
                response = await client.post(
                    f"{self.api_url}/search/random",
                    headers=self.headers,
                    json={"size": count * 3}  # Request more to filter for GPS
                )
                response.raise_for_status()
                assets = response.json()
                
                # Filter assets that have GPS coordinates
                photos_with_gps = []
                for asset in assets:
                    exif_info = asset.get("exifInfo", {})
                    if exif_info and exif_info.get("latitude") and exif_info.get("longitude"):
                        photos_with_gps.append({
                            "id": asset.get("id"),
                            "thumbnailUrl": f"{self.api_url}/assets/{asset.get('id')}/thumbnail",
                            "originalUrl": f"{self.api_url}/assets/{asset.get('id')}/original",
                            "latitude": exif_info.get("latitude"),
                            "longitude": exif_info.get("longitude"),
                            "city": exif_info.get("city"),
                            "state": exif_info.get("state"),
                            "country": exif_info.get("country"),
                            "dateTaken": exif_info.get("dateTimeOriginal"),
                        })
                        
                        if len(photos_with_gps) >= count:
                            break
                
                if len(photos_with_gps) < count:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Not enough photos with GPS coordinates found. Found {len(photos_with_gps)}, need {count}"
                    )
                
                return photos_with_gps[:count]
                
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
