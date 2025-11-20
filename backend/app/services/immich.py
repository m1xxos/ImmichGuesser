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
                # Use search/metadata to get assets with location data
                # Try to search for assets with coordinates
                response = await client.post(
                    f"{self.api_url}/search/metadata",
                    headers=self.headers,
                    json={
                        "isNotInAlbum": False,
                        "withExif": True,
                        "size": count * 20,  # Request many more to filter
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                # Get assets from response
                assets = result.get("assets", {}).get("items", []) if isinstance(result.get("assets"), dict) else result.get("assets", [])
                
                # Filter assets that have GPS coordinates
                photos_with_gps = []
                for asset in assets:
                    exif_info = asset.get("exifInfo", {})
                    if exif_info:
                        lat = exif_info.get("latitude")
                        lon = exif_info.get("longitude")
                        
                        # Check if coordinates exist and are not None/0
                        if lat and lon and lat != 0 and lon != 0:
                            asset_id = asset.get("id")
                            photos_with_gps.append({
                                "id": asset_id,
                                "thumbnailUrl": f"/game/photo/{asset_id}/preview",
                                "originalUrl": f"{self.api_url}/assets/{asset_id}/original",
                                "immichUrl": f"{self.api_url.replace('/api', '')}/photos/{asset_id}",
                                "latitude": lat,
                                "longitude": lon,
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
                        detail=f"Not enough photos with GPS coordinates found. Found {len(photos_with_gps)}, need {count}. Make sure your photos have GPS metadata in Immich and EXIF extraction is enabled."
                    )
                
                # Randomize the filtered photos
                import random
                random.shuffle(photos_with_gps)
                
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
