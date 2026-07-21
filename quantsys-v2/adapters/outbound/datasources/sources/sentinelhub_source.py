"""Sentinel Hub satellite imagery data source.

Provides satellite imagery for financial analysis and alternative data:
NDVI (vegetation health), NDWI (water detection), urban index, true/false color.

API Documentation: https://docs.sentinel-hub.com/
Authentication: OAuth2 with Client ID and Client Secret
Base URL: https://services.sentinel-hub.com/
"""

import os
import json
import base64
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)

# API constants
BASE_URL = "https://services.sentinel-hub.com"
TOKEN_URL = f"{BASE_URL}/oauth/token"
CATALOG_API_URL = f"{BASE_URL}/api/v1/catalog/1.0.0/search"
PROCESS_API_URL = f"{BASE_URL}/api/v1/process"

SENTINEL_2_L2A = "sentinel-2-l2a"
SENTINEL_1_GRD = "sentinel-1-grd"

EVALSCRIPTS = {
    "true_color": """
//VERSION=3
function setup() {
    return { input: ["B02", "B03", "B04"], output: { bands: 3 } };
}
function evaluatePixel(sample) {
    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}
""",
    "ndvi": """
//VERSION=3
function setup() {
    return { input: ["B04", "B08"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
    return [ndvi];
}
""",
    "ndwi": """
//VERSION=3
function setup() {
    return { input: ["B03", "B08"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
    let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
    return [ndwi];
}
""",
    "urban_index": """
//VERSION=3
function setup() {
    return { input: ["B11", "B08"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
    let ui = (sample.B11 - sample.B08) / (sample.B11 + sample.B08);
    return [ui];
}
""",
}


class SentinelHubSource(EconomicDataSource):
    """Sentinel Hub satellite imagery data source.

    Provides:
    - NDVI vegetation index (crop yield prediction, drought assessment)
    - NDWI water index (flood monitoring, water resources)
    - Urban index (construction tracking, urban sprawl)
    - True/false color imagery
    - Satellite scene catalog search

    Requires: SENTINELHUB_CLIENT_ID and SENTINELHUB_CLIENT_SECRET env vars.
    """

    def __init__(self):
        super().__init__(name="SentinelHub", requires_api_key=True)
        self.client_id = os.environ.get("SENTINELHUB_CLIENT_ID")
        self.client_secret = os.environ.get("SENTINELHUB_CLIENT_SECRET")
        self.session = SessionManager.get_session("sentinelhub")
        self._access_token = None
        self._token_expiry = None

    def validate_config(self) -> bool:
        if not self.client_id or not self.client_secret:
            logger.error("Sentinel Hub credentials not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="Credentials not configured. Set SENTINELHUB_CLIENT_ID and SENTINELHUB_CLIENT_SECRET."
            )
        try:
            auth_result = self._get_access_token()
            if "error" in auth_result:
                return DataSourceResponse.error_response(error=auth_result["error"])
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Sentinel Hub"},
                metadata={"source": "SentinelHub"}
            )
        except Exception as e:
            return handle_request_error(e, "SentinelHub", "test_connection")

    def _get_access_token(self) -> Dict[str, Any]:
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            return {"access_token": self._access_token}

        auth_bytes = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("ascii")).decode()
        headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            response = self.session.post(TOKEN_URL, headers=headers, data="grant_type=client_credentials", timeout=30)
            response.raise_for_status()
            token_data = response.json()
            self._access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            return {"access_token": self._access_token, "expires_in": expires_in}
        except Exception as e:
            return {"error": f"Authentication failed: {str(e)}"}

    def _get_auth_headers(self) -> Dict[str, str]:
        token_result = self._get_access_token()
        if "error" in token_result:
            return {"error": token_result["error"]}
        return {
            "Authorization": f"Bearer {token_result['access_token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_series(self, series_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> DataSourceResponse:
        return self.search_imagery_by_coordinates(lat=35.0, lon=105.0, start_date=start_date, end_date=end_date)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        return self.get_available_collections()

    def get_available_collections(self) -> DataSourceResponse:
        """Get available satellite collections with descriptions."""
        collections = [
            {
                "id": SENTINEL_2_L2A, "name": "Sentinel-2 Level-2A",
                "description": "High-res optical imagery, atmospheric correction",
                "resolution": "10m/20m/60m", "revisit_time": "5 days",
                "use_cases": ["Vegetation", "Land cover", "Coastal areas"],
            },
            {
                "id": SENTINEL_1_GRD, "name": "Sentinel-1 GRD",
                "description": "Radar imagery - works day/night through clouds",
                "resolution": "5x20m", "revisit_time": "1-3 days",
                "use_cases": ["Flood monitoring", "Oil spill detection", "Ship detection"],
            },
        ]
        return DataSourceResponse.success_response(
            data=collections, metadata={"source": "SentinelHub", "count": len(collections)}
        )

    def get_evalscript_types(self) -> DataSourceResponse:
        """Get available image processing types."""
        types = [
            {"id": "true_color", "name": "True Color", "use_cases": ["Visual inspection", "Human geography"]},
            {"id": "ndvi", "name": "NDVI Vegetation Index", "range": "-1 to 1",
             "use_cases": ["Crop monitoring", "Drought assessment", "Yield prediction"]},
            {"id": "ndwi", "name": "NDWI Water Index", "range": "-1 to 1",
             "use_cases": ["Flood monitoring", "Water resources", "Coastal change"]},
            {"id": "urban_index", "name": "Urban Index", "range": "-1 to 1",
             "use_cases": ["Urban sprawl", "Construction tracking", "Infrastructure planning"]},
        ]
        return DataSourceResponse.success_response(
            data=types, metadata={"source": "SentinelHub", "count": len(types)}
        )

    def search_imagery(
        self,
        bbox: List[float],
        datetime_range: str,
        collections: Optional[List[str]] = None,
        max_cloud_cover: float = 30.0,
        limit: int = 10,
    ) -> DataSourceResponse:
        """Search for available satellite imagery.

        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat]
            datetime_range: "YYYY-MM-DDTHH:MM:SSZ/YYYY-MM-DDTHH:MM:SSZ"
            collections: Satellite collections to search (default: S2-L2A)
            max_cloud_cover: Max cloud % (default 30)
            limit: Max scenes (default 10)
        """
        self._log_request("search_imagery", {"bbox": bbox, "datetime_range": datetime_range})
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        if not bbox or len(bbox) != 4:
            return DataSourceResponse.error_response(error="bbox must be [min_lon, min_lat, max_lon, max_lat]")

        if not collections:
            collections = [SENTINEL_2_L2A]

        try:
            headers = self._get_auth_headers()
            if "error" in headers:
                return DataSourceResponse.error_response(error=headers["error"])

            search_params = {
                "bbox": bbox, "datetime": datetime_range, "collections": collections,
                "limit": limit, "query": {"eo:cloud_cover": {"lt": max_cloud_cover}},
            }
            response = self.session.post(CATALOG_API_URL, headers=headers, json=search_params, timeout=60)
            response.raise_for_status()
            raw = response.json()

            features = raw.get("features", [])
            scenes = []
            for f in features:
                scenes.append({
                    "id": f.get("id"), "datetime": f.get("properties", {}).get("datetime"),
                    "cloud_cover": f.get("properties", {}).get("eo:cloud_cover", 0),
                    "bbox": f.get("bbox"), "geometry": f.get("geometry"),
                })

            self._log_success("search_imagery", len(scenes))
            return DataSourceResponse.success_response(
                data=scenes,
                metadata={"source": "SentinelHub", "total_scenes": len(scenes),
                          "bbox": bbox, "collections": collections}
            )
        except Exception as e:
            return handle_request_error(e, "SentinelHub", "search_imagery")

    def search_imagery_by_coordinates(
        self,
        lat: float,
        lon: float,
        radius_km: float = 10.0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_cloud_cover: float = 30.0,
        limit: int = 10,
    ) -> DataSourceResponse:
        """Search satellite imagery by center point and radius.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius_km: Search radius in km
            start_date: Start date YYYY-MM-DD (default: 30 days ago)
            end_date: End date YYYY-MM-DD (default: today)
        """
        self._log_request("search_imagery_by_coordinates", {"lat": lat, "lon": lon, "radius_km": radius_km})
        try:
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / (111.0 * abs(lat) if lat != 0 else 111.0)
            bbox = [lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta]

            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

            datetime_range = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"
            result = self.search_imagery(bbox, datetime_range, max_cloud_cover=max_cloud_cover, limit=limit)
            if result.success and result.metadata:
                result.metadata.update({"search_center": {"lat": lat, "lon": lon}, "radius_km": radius_km})
            return result
        except Exception as e:
            return handle_request_error(e, "SentinelHub", "search_imagery_by_coordinates")

    def process_imagery(
        self,
        bbox: List[float],
        datetime_range: str,
        evalscript_type: str = "true_color",
        width: int = 512,
        height: int = 512,
    ) -> DataSourceResponse:
        """Process and download satellite imagery.

        Args:
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
            datetime_range: ISO datetime range
            evalscript_type: One of: true_color, ndvi, ndwi, urban_index
            width: Output image width
            height: Output image height
        """
        self._log_request("process_imagery", {"bbox": bbox, "evalscript": evalscript_type})
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        evalscript = EVALSCRIPTS.get(evalscript_type, EVALSCRIPTS["true_color"])
        try:
            headers = self._get_auth_headers()
            if "error" in headers:
                return DataSourceResponse.error_response(error=headers["error"])

            parts = datetime_range.split("/")
            process_params = {
                "input": {
                    "bounds": {"bbox": bbox},
                    "data": [{
                        "type": SENTINEL_2_L2A,
                        "dataFilter": {"timeRange": {"from": parts[0], "to": parts[1]},
                                       "maxCloudCoverage": 30}
                    }]
                },
                "output": {"width": width, "height": height,
                           "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
                "evalscript": evalscript,
            }

            proc_headers = headers.copy()
            proc_headers["Accept"] = "image/*"
            response = self.session.post(PROCESS_API_URL, headers=proc_headers, json=process_params, timeout=60)
            response.raise_for_status()

            image_b64 = base64.b64encode(response.content).decode("utf-8")
            return DataSourceResponse.success_response(
                data={
                    "image_base64": image_b64,
                    "content_type": response.headers.get("content-type", "image/png"),
                    "size_bytes": len(response.content),
                },
                metadata={"source": "SentinelHub", "evalscript": evalscript_type,
                          "bbox": bbox, "width": width, "height": height,
                          "timestamp": datetime.utcnow().isoformat()}
            )
        except Exception as e:
            return handle_request_error(e, "SentinelHub", "process_imagery")

    def get_ndvi_for_region(
        self, lat: float, lon: float, radius_km: float = 10.0,
        start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get NDVI vegetation index for a region.

        Useful for: crop yield prediction, drought assessment, supply chain risk.
        """
        self._log_request("get_ndvi_for_region", {"lat": lat, "lon": lon})
        try:
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / (111.0 * abs(lat) if lat != 0 else 111.0)
            bbox = [lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta]

            if not end_date:
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

            datetime_range = f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"
            return self.process_imagery(bbox, datetime_range, evalscript_type="ndvi")
        except Exception as e:
            return handle_request_error(e, "SentinelHub", "get_ndvi_for_region")
