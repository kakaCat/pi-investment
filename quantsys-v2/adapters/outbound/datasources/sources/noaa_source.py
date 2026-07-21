"""NOAA climate and environmental data source.

Provides access to weather, climate, and environmental indicators with economic impact.

No API key required (uses public NOAA APIs).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NOAAEconomicSource(EconomicDataSource):
    """NOAA climate and environmental economic indicators data source.

    Provides access to:
    - Weather/climate data (temperature, precipitation)
    - Climate normals and anomalies
    - Billion-dollar disaster events (US)
    - Drought monitor (economic impact)
    - Climate Prediction Center outlooks
    - Agricultural weather indices
    - Energy demand weather indicators (HDD/CDD)

    Critical for: agricultural commodity forecasting, energy demand,
    insurance/reinsurance risk, supply chain disruption modeling.
    No API key required (free public API token available).
    """

    BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
    NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"

    DISASTER_TYPES = [
        "drought", "flooding", "freeze", "severe_storm",
        "tropical_cyclone", "wildfire", "winter_storm"
    ]

    CLIMATE_PARAMETERS = [
        "TAVG",   # Average temperature
        "TMAX",   # Maximum temperature
        "TMIN",   # Minimum temperature
        "PRCP",   # Precipitation
        "SNOW",   # Snowfall
        "SNWD",   # Snow depth
        "AWND",   # Average wind speed
        "WSF5",   # Fastest 5-second wind speed
    ]

    def __init__(self, api_token: Optional[str] = None):
        """Initialize NOAA data source.

        Args:
            api_token: NOAA CDO API token (free from https://www.ncdc.noaa.gov/cdo-web/token)
        """
        super().__init__(name="NOAA", requires_api_key=False)
        self.api_token = api_token
        self.session = SessionManager.get_session("noaa")
        if self.api_token:
            self.session.headers.update({"token": self.api_token})

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/datasets",
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NOAA_CDO"},
                metadata={"source": "NOAA", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"NOAA connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_billion_dollar_disasters(self) -> DataSourceResponse:
        """Get US billion-dollar weather and climate disasters.

        Critical for insurance/reinsurance sector analysis and economic
        impact assessment of climate events.

        Returns:
            DataSourceResponse with disaster event data
        """
        try:
            response = self.session.get(
                f"{self.NCEI_URL}",
                params={
                    "dataset": "billion-dollar-disasters",
                    "dataType": "events",
                    "format": "json"
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "NOAA_NCEI",
                    "dataset": "billion_dollar_disasters",
                    "note": "Economic impact of climate/weather disasters"
                }
            )
        except Exception as e:
            return handle_request_error(e, "NOAA", "get_billion_dollar_disasters")

    def get_climate_data(
        self,
        station_id: str,
        data_type: str = "TAVG",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get climate data for a station.

        Args:
            station_id: NOAA station ID (e.g., 'GHCND:USW00014739' for Boston)
            data_type: Data type (TAVG, TMAX, TMIN, PRCP, SNOW)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with climate data
        """
        try:
            params: Dict[str, Any] = {
                "datasetid": "GHCND",
                "stationid": station_id,
                "datatypeid": data_type,
                "limit": 1000,
                "units": "metric"
            }
            if start_date:
                params["startdate"] = start_date
            if end_date:
                params["enddate"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/data",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "NOAA_CDO",
                    "station_id": station_id,
                    "data_type": data_type,
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "NOAA", "get_climate_data")

    def get_energy_demand_indicators(
        self,
        location: str = "US"
    ) -> DataSourceResponse:
        """Get heating and cooling degree days for energy demand analysis.

        HDD/CDD are the primary weather-driven energy demand indicators:
        - HDD: Heating Degree Days (natural gas demand proxy)
        - CDD: Cooling Degree Days (electricity demand proxy)

        Args:
            location: Region code (default: US)

        Returns:
            DataSourceResponse with degree day data
        """
        try:
            response = self.session.get(
                f"{self.NCEI_URL}",
                params={
                    "dataset": "climate-normals",
                    "dataType": "degree-days",
                    "location": location,
                    "format": "json"
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "NOAA_NCEI",
                    "location": location,
                    "indicators": ["HDD", "CDD"],
                    "use": "energy_demand_proxy"
                }
            )
        except Exception as e:
            return handle_request_error(e, "NOAA", "get_energy_demand_indicators")

    def get_drought_monitor(self) -> DataSourceResponse:
        """Get US Drought Monitor data.

        Important for agricultural commodity pricing, water utility stocks,
        and regional economic impact assessment.

        Returns:
            DataSourceResponse with drought data
        """
        try:
            response = self.session.get(
                f"{self.NCEI_URL}",
                params={
                    "dataset": "drought-monitor",
                    "dataType": "county",
                    "format": "json"
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "NOAA_NCEI",
                    "dataset": "drought_monitor",
                    "note": "Agricultural and hydrological drought indicators"
                }
            )
        except Exception as e:
            return handle_request_error(e, "NOAA", "get_drought_monitor")

    def get_climate_parameters(self) -> DataSourceResponse:
        """Get available climate data parameters.

        Returns:
            DataSourceResponse with parameter list
        """
        return DataSourceResponse.success_response(
            data=self.CLIMATE_PARAMETERS,
            metadata={"source": "NOAA", "count": len(self.CLIMATE_PARAMETERS)}
        )

    def get_disaster_types(self) -> DataSourceResponse:
        """Get disaster event types.

        Returns:
            DataSourceResponse with disaster type list
        """
        return DataSourceResponse.success_response(
            data=self.DISASTER_TYPES,
            metadata={"source": "NOAA", "count": len(self.DISASTER_TYPES)}
        )
