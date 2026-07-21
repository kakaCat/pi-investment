"""NASA GIBS (Global Imagery Browse Services) earth observation data source.

Provides access to satellite imagery and earth observation data for
environmental monitoring and economic analysis. No API key required.
"""

from typing import Optional, Dict, Any
import logging
from datetime import datetime

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NASAGIBSSource(EconomicDataSource):
    """NASA Global Imagery Browse Services data source.

    Provides access to MODIS/VIIRS satellite imagery including nightlights
    (GDP proxy), vegetation indices (crop yield), land/sea temperature,
    aerosol optical depth, snow cover, and active fire detection.

    No API key required.
    """

    BASE_URL = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
    GIBS_API = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0"

    LAYERS = {
        "viirs_nightlights": {
            "id": "VIIRS_SNPP_DayNightBand_ENCC",
            "description": "VIIRS nightlight radiance (GDP/economic proxy)",
            "resolution": "500m",
        },
        "ndvi": {
            "id": "MODIS_Terra_NDVI_8Day",
            "description": "NDVI vegetation index (crop yield proxy)",
            "resolution": "250m",
        },
        "land_surface_temp": {
            "id": "MODIS_Terra_Land_Surface_Temp_Day",
            "description": "Land surface temperature daytime",
            "resolution": "1km",
        },
        "aerosol": {
            "id": "MODIS_Terra_Aerosol",
            "description": "Aerosol optical depth (air quality)",
            "resolution": "10km",
        },
        "sea_surface_temp": {
            "id": "MODIS_Terra_Sea_Surface_Temp",
            "description": "Sea surface temperature",
            "resolution": "4km",
        },
        "snow_cover": {
            "id": "MODIS_Terra_Snow_Cover",
            "description": "Snow and ice cover extent",
            "resolution": "500m",
        },
        "active_fires": {
            "id": "MODIS_Terra_Thermal_Anomalies",
            "description": "Active fire / thermal anomaly detection",
            "resolution": "1km",
        },
    }

    def __init__(self):
        super().__init__(name="NASAGIBS", requires_api_key=False)
        self.session = SessionManager.get_session("nasa_gibs")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.GIBS_API}/WMTSCapabilities.xml", timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NASA_GIBS"},
                metadata={"source": "NASAGIBS", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"NASA GIBS connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_layer_list(self) -> DataSourceResponse:
        layers = [
            {"name": n, "layer_id": i["id"], "description": i["description"],
             "resolution": i["resolution"]}
            for n, i in self.LAYERS.items()
        ]
        return DataSourceResponse.success_response(
            data=layers, metadata={"source": "NASAGIBS", "count": len(layers)}
        )

    def get_tile_url(
        self,
        layer_name: str,
        zoom: int = 3,
        tile_row: int = 0,
        tile_col: int = 0,
        date: Optional[str] = None,
    ) -> DataSourceResponse:
        try:
            if layer_name not in self.LAYERS:
                return DataSourceResponse.error_response(
                    error=f"Unknown layer: {layer_name}. Use get_layer_list()."
                )
            layer = self.LAYERS[layer_name]
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            tile_url = (
                f"{self.BASE_URL}/{layer['id']}/default/{date}"
                f"/GoogleMapsCompatible_Level{zoom}/{tile_row}/{tile_col}.png"
            )
            return DataSourceResponse.success_response(
                data={"tile_url": tile_url, "layer": layer_name, "date": date,
                      "zoom": zoom, "tile_row": tile_row, "tile_col": tile_col},
                metadata={"source": "NASAGIBS", "layer": layer_name, "date": date},
            )
        except Exception as e:
            return handle_request_error(e, "NASAGIBS", "get_tile_url")

    def get_nightlight_metadata(self) -> DataSourceResponse:
        layer = self.LAYERS["viirs_nightlights"]
        return DataSourceResponse.success_response(
            data={
                "layer_id": layer["id"],
                "description": layer["description"],
                "resolution": layer["resolution"],
                "note": "Nightlight radiance correlates with GDP at subnational level.",
            },
            metadata={"source": "NASAGIBS", "layer": "viirs_nightlights"},
        )

    def get_vegetation_metadata(self) -> DataSourceResponse:
        layer = self.LAYERS["ndvi"]
        return DataSourceResponse.success_response(
            data={
                "layer_id": layer["id"],
                "description": layer["description"],
                "resolution": layer["resolution"],
                "note": "NDVI 8-day composite. Values -0.2 to 1.0. Higher = denser vegetation.",
            },
            metadata={"source": "NASAGIBS", "layer": "ndvi"},
        )
