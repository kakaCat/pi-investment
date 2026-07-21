"""Copernicus earth observation and climate data source.

Provides access to the EU Copernicus programme: atmosphere, marine, land,
climate change, and emergency management data. Free and open data policy.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CopernicusSource(EconomicDataSource):
    """Copernicus earth observation and climate monitoring data source.

    Provides access to CAMS (Atmosphere), C3S (Climate Change), CMEMS (Marine),
    CLMS (Land), and CEMS (Emergency) services.

    Economic relevance: renewable energy forecasting (solar/wind),
    agricultural monitoring, climate risk assessment, carbon monitoring.
    Free and open data policy.
    """

    BASE_URL = "https://climate.copernicus.eu/api"
    CDS_URL = "https://cds.climate.copernicus.eu/api"
    ADS_URL = "https://ads.atmosphere.copernicus.eu/api"

    ERA5_VARIABLES = {
        "solar_radiation": "Surface solar radiation downwards (SSRD)",
        "wind_100m": "100m wind speed - wind energy potential",
        "temperature_2m": "2m temperature - energy demand/agriculture",
        "precipitation": "Total precipitation - water resources",
        "soil_moisture": "Volumetric soil water layer 1 - crop monitoring",
        "snow_depth": "Snow depth - hydropower/winter tourism",
    }

    SERVICES = ["CAMS", "C3S", "CMEMS", "CLMS", "CEMS"]

    def __init__(self):
        super().__init__(name="Copernicus", requires_api_key=False)
        self.session = SessionManager.get_session("copernicus")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(f"{self.CDS_URL}/v2", timeout=10)
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Copernicus_CDS"},
                metadata={"source": "Copernicus", "base_url": self.CDS_URL},
            )
        except Exception as e:
            logger.error(f"Copernicus connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_services(self) -> DataSourceResponse:
        services = [
            {"name": "CAMS", "description": "Atmosphere (air quality, GHGs, UV, solar)"},
            {"name": "C3S", "description": "Climate change (reanalysis, projections)"},
            {"name": "CMEMS", "description": "Marine environment (ocean state, waves)"},
            {"name": "CLMS", "description": "Land monitoring (land cover, vegetation)"},
            {"name": "CEMS", "description": "Emergency management (floods, fires, droughts)"},
        ]
        return DataSourceResponse.success_response(
            data=services, metadata={"source": "Copernicus", "count": len(services)}
        )

    def get_era5_variables(self) -> DataSourceResponse:
        variables = [
            {"variable": n, "description": d}
            for n, d in self.ERA5_VARIABLES.items()
        ]
        return DataSourceResponse.success_response(
            data=variables,
            metadata={"source": "Copernicus_C3S", "dataset": "ERA5", "count": len(variables)},
        )

    def get_solar_radiation_data(
        self, latitude: float = 51.5, longitude: float = 0.0, year: int = 2024
    ) -> DataSourceResponse:
        try:
            params = {
                "variable": "surface_solar_radiation_downwards",
                "year": year, "latitude": latitude, "longitude": longitude,
                "format": "json",
            }
            response = self.session.get(
                f"{self.CDS_URL}/retrieve/v1/era5-single-levels",
                params=params, timeout=60,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={
                    "source": "Copernicus_C3S", "dataset": "ERA5",
                    "variable": "solar_radiation",
                    "location": {"lat": latitude, "lon": longitude},
                    "year": year, "unit": "J/m²",
                },
            )
        except Exception as e:
            return handle_request_error(e, "Copernicus", "get_solar_radiation_data")

    def get_wind_data(
        self, latitude: float = 51.5, longitude: float = 0.0, year: int = 2024
    ) -> DataSourceResponse:
        try:
            params = {
                "variable": "100m_wind_speed",
                "year": year, "latitude": latitude, "longitude": longitude,
                "format": "json",
            }
            response = self.session.get(
                f"{self.CDS_URL}/retrieve/v1/era5-single-levels",
                params=params, timeout=60,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={
                    "source": "Copernicus_C3S", "dataset": "ERA5",
                    "variable": "wind_speed_100m",
                    "location": {"lat": latitude, "lon": longitude},
                    "year": year, "unit": "m/s",
                },
            )
        except Exception as e:
            return handle_request_error(e, "Copernicus", "get_wind_data")

    def get_atmosphere_data(
        self, variable: str = "pm2_5", region: str = "europe"
    ) -> DataSourceResponse:
        try:
            params = {"variable": variable, "region": region, "format": "json"}
            response = self.session.get(
                f"{self.ADS_URL}/retrieve/v1/cams-europe-air-quality",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Copernicus_CAMS", "variable": variable, "region": region},
            )
        except Exception as e:
            return handle_request_error(e, "Copernicus", "get_atmosphere_data")

    def get_climate_projections(
        self, scenario: str = "ssp585", variable: str = "temperature",
        horizon: str = "2081-2100",
    ) -> DataSourceResponse:
        try:
            params = {
                "scenario": scenario, "variable": variable,
                "horizon": horizon, "format": "json",
            }
            response = self.session.get(
                f"{self.CDS_URL}/retrieve/v1/cmip6-projections",
                params=params, timeout=60,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={
                    "source": "Copernicus_C3S", "dataset": "CMIP6",
                    "scenario": scenario, "variable": variable, "horizon": horizon,
                },
            )
        except Exception as e:
            return handle_request_error(e, "Copernicus", "get_climate_projections")
