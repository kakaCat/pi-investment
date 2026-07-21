"""Data source implementations — 60+ sources."""

# Original
from adapters.outbound.datasources.sources.akshare_source import AkShareSource
from adapters.outbound.datasources.sources.fred_source import FREDSource
from adapters.outbound.datasources.sources.world_bank_source import WorldBankSource
from adapters.outbound.datasources.sources.yahoo_finance_source import YahooFinanceSource
from adapters.outbound.datasources.sources.binance_source import BinanceSource
from adapters.outbound.datasources.sources.polygon_source import PolygonSource

# Phase 1: Macroeconomic data sources
from adapters.outbound.datasources.sources.imf_source import IMFSource
from adapters.outbound.datasources.sources.oecd_source import OECDSource
from adapters.outbound.datasources.sources.bis_source import BISSource
from adapters.outbound.datasources.sources.ecb_source import ECBSource
from adapters.outbound.datasources.sources.boj_source import BOJSource

# Phase 2: Market data sources
from adapters.outbound.datasources.sources.alphavantage_source import AlphaVantageSource
from adapters.outbound.datasources.sources.finnhub_source import FinnhubSource
from adapters.outbound.datasources.sources.iexcloud_source import IEXCloudSource
from adapters.outbound.datasources.sources.tiingo_source import TiingoSource
from adapters.outbound.datasources.sources.nasdaqdatalink_source import NasdaqDataLinkSource

# Phase 3: Unified Crypto Exchange (optional dependency)
try:
    from adapters.outbound.datasources.sources.crypto_exchange_source import CryptoExchangeSource
except ImportError:
    CryptoExchangeSource = None

# Expansion Phase 1: 16 more sources
from adapters.outbound.datasources.sources.glassnode_source import GlassnodeSource
from adapters.outbound.datasources.sources.coinglass_source import CoinglassSource
from adapters.outbound.datasources.sources.coinpaprika_source import CoinpaprikaSource
from adapters.outbound.datasources.sources.messari_source import MessariSource
from adapters.outbound.datasources.sources.dexscreener_source import DexscreenerSource
from adapters.outbound.datasources.sources.waqi_source import WAQISource
from adapters.outbound.datasources.sources.opencorporates_source import OpenCorporatesSource
from adapters.outbound.datasources.sources.ons_source import ONSSource
from adapters.outbound.datasources.sources.scb_source import SCBSource
from adapters.outbound.datasources.sources.rba_source import RBASource
from adapters.outbound.datasources.sources.adb_source import ADBSource
from adapters.outbound.datasources.sources.afdb_source import AfDBSource
from adapters.outbound.datasources.sources.stooq_source import StooqSource
from adapters.outbound.datasources.sources.opec_source import OPECSource
from adapters.outbound.datasources.sources.ebrd_source import EBRDSource
from adapters.outbound.datasources.sources.intrinio_source import IntrinioSource

# Expansion Phase 2: 11 more sources
from adapters.outbound.datasources.sources.cme_grain_source import CMEGrainSource
from adapters.outbound.datasources.sources.marketstack_source import MarketstackSource
from adapters.outbound.datasources.sources.reliefweb_source import ReliefWebSource
from adapters.outbound.datasources.sources.opensecrets_source import OpenSecretsSource
from adapters.outbound.datasources.sources.un_sdg_source import UNSDGSource
from adapters.outbound.datasources.sources.undp_source import UNDPSource
from adapters.outbound.datasources.sources.unep_source import UNEPSource
from adapters.outbound.datasources.sources.arxiv_source import ArxivSource
from adapters.outbound.datasources.sources.nber_source import NBERSource
from adapters.outbound.datasources.sources.crossref_source import CrossrefSource
from adapters.outbound.datasources.sources.numbeo_source import NumbeoSource

# Expansion Phase 3: 5 more sources
from adapters.outbound.datasources.sources.lme_source import LMESource
from adapters.outbound.datasources.sources.entsoe_source import ENTSOESource
from adapters.outbound.datasources.sources.fmp_source import FMPSource
from adapters.outbound.datasources.sources.weforum_source import WEForumSource
from adapters.outbound.datasources.sources.fiscal_data_source import FiscalDataSource

# Others
from adapters.outbound.datasources.sources.sentinelhub_source import SentinelHubSource
from adapters.outbound.datasources.sources.n2yo_source import N2YOSource
from adapters.outbound.datasources.sources.nasa_gibs_source import NASAGIBSSource
from adapters.outbound.datasources.sources.copernicus_source import CopernicusSource
from adapters.outbound.datasources.sources.oscar_source import OSCARSource

# Expansion Phase 4: 11 more sources
from adapters.outbound.datasources.sources.marinetraffic_source import MarineTrafficSource
from adapters.outbound.datasources.sources.fitchconnect_source import FitchConnectSource
from adapters.outbound.datasources.sources.wits_source import WITSSource
from adapters.outbound.datasources.sources.swift_source import SWIFTSource
from adapters.outbound.datasources.sources.gleif_source import GLEIFSource
from adapters.outbound.datasources.sources.carbon_source import CarbonSource
from adapters.outbound.datasources.sources.wipo_source import WIPOSource
from adapters.outbound.datasources.sources.unctad_source import UNCTADSource
from adapters.outbound.datasources.sources.global_trade_alert_source import GlobalTradeAlertSource
from adapters.outbound.datasources.sources.boc_source import BankOfCanadaSource
from adapters.outbound.datasources.sources.noaa_source import NOAAEconomicSource

# Expansion Phase 5: 35 more sources (100+ total)
from adapters.outbound.datasources.sources.cftc_cot_source import CFTCCommitmentOfTradersSource
from adapters.outbound.datasources.sources.sec_edgar_source import SECEDGARSource
from adapters.outbound.datasources.sources.boe_source import BankOfEnglandSource
from adapters.outbound.datasources.sources.pbc_source import PeopleBankOfChinaSource
from adapters.outbound.datasources.sources.bcb_source import BancoCentralBrasilSource
from adapters.outbound.datasources.sources.eurostat_source import EurostatSource
from adapters.outbound.datasources.sources.eia_source import EIASource
from adapters.outbound.datasources.sources.iea_source import InternationalEnergyAgencySource
from adapters.outbound.datasources.sources.fao_source import FAOSource
from adapters.outbound.datasources.sources.usda_source import USDAAgriculturalSource
from adapters.outbound.datasources.sources.gdelt_source import GDELTSource
from adapters.outbound.datasources.sources.google_trends_source import GoogleTrendsSource
from adapters.outbound.datasources.sources.baltic_exchange_source import BalticExchangeSource
from adapters.outbound.datasources.sources.openweather_source import OpenWeatherSource
from adapters.outbound.datasources.sources.aviationstack_source import AviationStackSource
from adapters.outbound.datasources.sources.github_activity_source import GitHubActivitySource
from adapters.outbound.datasources.sources.wikipedia_stats_source import WikipediaStatsSource
from adapters.outbound.datasources.sources.tradingeconomics_source import TradingEconomicsSource
from adapters.outbound.datasources.sources.zillow_source import ZillowRealEstateSource
from adapters.outbound.datasources.sources.opentable_source import OpenTableSource
from adapters.outbound.datasources.sources.rbi_source import ReserveBankIndiaSource
from adapters.outbound.datasources.sources.statcan_source import StatisticsCanadaSource
from adapters.outbound.datasources.sources.abs_source import AustralianBureauStatisticsSource
from adapters.outbound.datasources.sources.openaq_source import OpenAQSource
from adapters.outbound.datasources.sources.apple_mobility_source import AppleMobilitySource
from adapters.outbound.datasources.sources.bp_energy_source import BPStatisticalReviewSource
from adapters.outbound.datasources.sources.worldsteel_source import WorldSteelAssociationSource
from adapters.outbound.datasources.sources.worldgold_source import WorldGoldCouncilSource
from adapters.outbound.datasources.sources.debank_source import DeBankSource
from adapters.outbound.datasources.sources.defillama_source import DefiLlamaSource
from adapters.outbound.datasources.sources.event_registry_source import EventRegistrySource
from adapters.outbound.datasources.sources.un_population_source import UNPopulationSource
from adapters.outbound.datasources.sources.futures_term_structure_source import FuturesTermStructureSource
from adapters.outbound.datasources.sources.dune_analytics_source import DuneAnalyticsSource
from adapters.outbound.datasources.sources.ngfs_climate_source import NGFSClimateSource

# Tier 1: Central Banks (12)
from adapters.outbound.datasources.sources.bnm_source import BNMSource
from adapters.outbound.datasources.sources.bnr_source import BNRSource
from adapters.outbound.datasources.sources.boi_source import BankOfIsraelSource
from adapters.outbound.datasources.sources.cnb_source import CNBSource
from adapters.outbound.datasources.sources.federal_reserve_source import FederalReserveSource
from adapters.outbound.datasources.sources.hnb_source import HNBSource
from adapters.outbound.datasources.sources.mnb_source import MNBSource
from adapters.outbound.datasources.sources.nbp_source import NBPSource
from adapters.outbound.datasources.sources.norges_bank_source import NorgesBankSource
from adapters.outbound.datasources.sources.riksbank_source import RiksbankSource
from adapters.outbound.datasources.sources.snb_source import SNBSource
from adapters.outbound.datasources.sources.tcmb_source import TCMBSource

# Tier 1: US Economic Agencies (3)
from adapters.outbound.datasources.sources.bea_source import BEASource
from adapters.outbound.datasources.sources.bls_source import BLSSource
from adapters.outbound.datasources.sources.census_source import CensusSource

# Tier 1: Market Data (10)
from adapters.outbound.datasources.sources.cboe_vix_source import CBOEVIXSource
from adapters.outbound.datasources.sources.databento_source import DatabentoSource
from adapters.outbound.datasources.sources.eodhd_source import EODHDSource
from adapters.outbound.datasources.sources.simfin_source import SimFinSource
from adapters.outbound.datasources.sources.tradingview_source import TradingViewSource
from adapters.outbound.datasources.sources.twelve_data_source import TwelveDataSource
from adapters.outbound.datasources.sources.comex_source import COMEXSource
from adapters.outbound.datasources.sources.nymex_source import NYMEXSource
from adapters.outbound.datasources.sources.frankfurter_source import FrankfurterSource
from adapters.outbound.datasources.sources.openfigi_source import OpenFIGISource

# Tier 1: Energy Deep-Dive (7)
from adapters.outbound.datasources.sources.eia_electricity_source import EIAElectricitySource
from adapters.outbound.datasources.sources.eia_natural_gas_source import EIANaturalGasSource
from adapters.outbound.datasources.sources.eia_petroleum_source import EIAPetroleumSource
from adapters.outbound.datasources.sources.eia_steo_source import EIASTEOSource
from adapters.outbound.datasources.sources.platts_source import PlattsSource
from adapters.outbound.datasources.sources.irena_source import IRENASource
from adapters.outbound.datasources.sources.ember_energy_source import EmberEnergySource

# Tier 1: Shipping/Transport (3)
from adapters.outbound.datasources.sources.freightos_source import FreightosSource
from adapters.outbound.datasources.sources.port_congestion_source import PortCongestionSource
from adapters.outbound.datasources.sources.aisstream_source import AISStreamSource

# Prediction Markets
from adapters.outbound.datasources.sources.polymarket_source import PolymarketSource
from adapters.outbound.datasources.sources.kalshi_source import KalshiSource

__all__ = [
    # Original
    "AkShareSource",
    "FREDSource",
    "WorldBankSource",
    "YahooFinanceSource",
    "BinanceSource",
    "PolygonSource",
    # Phase 1: Macro
    "IMFSource",
    "OECDSource",
    "BISSource",
    "ECBSource",
    "BOJSource",
    # Phase 2: Market
    "AlphaVantageSource",
    "FinnhubSource",
    "IEXCloudSource",
    "TiingoSource",
    "NasdaqDataLinkSource",
    # Phase 3: Crypto
    "CryptoExchangeSource",
    # Expansion Phase 1
    "GlassnodeSource",
    "CoinglassSource",
    "CoinpaprikaSource",
    "MessariSource",
    "DexscreenerSource",
    "WAQISource",
    "OpenCorporatesSource",
    "ONSSource",
    "SCBSource",
    "RBASource",
    "ADBSource",
    "AfDBSource",
    "StooqSource",
    "OPECSource",
    "EBRDSource",
    "IntrinioSource",
    # Expansion Phase 2
    "CMEGrainSource",
    "MarketstackSource",
    "ReliefWebSource",
    "OpenSecretsSource",
    "UNSDGSource",
    "UNDPSource",
    "UNEPSource",
    "ArxivSource",
    "NBERSource",
    "CrossrefSource",
    "NumbeoSource",
    # Expansion Phase 3
    "LMESource",
    "ENTSOESource",
    "FMPSource",
    "WEForumSource",
    "FiscalDataSource",
    # Others
    "SentinelHubSource",
    "N2YOSource",
    "NASAGIBSSource",
    "CopernicusSource",
    "OSCARSource",
    # Expansion Phase 4
    "MarineTrafficSource",
    "FitchConnectSource",
    "WITSSource",
    "SWIFTSource",
    "GLEIFSource",
    "CarbonSource",
    "WIPOSource",
    "UNCTADSource",
    "GlobalTradeAlertSource",
    "BankOfCanadaSource",
    "NOAAEconomicSource",
    # Expansion Phase 5
    "CFTCCommitmentOfTradersSource",
    "SECEDGARSource",
    "BankOfEnglandSource",
    "PeopleBankOfChinaSource",
    "BancoCentralBrasilSource",
    "EurostatSource",
    "EIASource",
    "InternationalEnergyAgencySource",
    "FAOSource",
    "USDAAgriculturalSource",
    "GDELTSource",
    "GoogleTrendsSource",
    "BalticExchangeSource",
    "OpenWeatherSource",
    "AviationStackSource",
    "GitHubActivitySource",
    "WikipediaStatsSource",
    "TradingEconomicsSource",
    "ZillowRealEstateSource",
    "OpenTableSource",
    "ReserveBankIndiaSource",
    "StatisticsCanadaSource",
    "AustralianBureauStatisticsSource",
    "OpenAQSource",
    "AppleMobilitySource",
    "BPStatisticalReviewSource",
    "WorldSteelAssociationSource",
    "WorldGoldCouncilSource",
    "DeBankSource",
    "DefiLlamaSource",
    "EventRegistrySource",
    "UNPopulationSource",
    "FuturesTermStructureSource",
    "DuneAnalyticsSource",
    "NGFSClimateSource",
    # Tier 1: Central Banks (12)
    "BNMSource",
    "BNRSource",
    "BankOfIsraelSource",
    "CNBSource",
    "FederalReserveSource",
    "HNBSource",
    "MNBSource",
    "NBPSource",
    "NorgesBankSource",
    "RiksbankSource",
    "SNBSource",
    "TCMBSource",
    # Tier 1: US Economic Agencies (3)
    "BEASource",
    "BLSSource",
    "CensusSource",
    # Tier 1: Market Data (10)
    "CBOEVIXSource",
    "DatabentoSource",
    "EODHDSource",
    "SimFinSource",
    "TradingViewSource",
    "TwelveDataSource",
    "COMEXSource",
    "NYMEXSource",
    "FrankfurterSource",
    "OpenFIGISource",
    # Tier 1: Energy Deep-Dive (7)
    "EIAElectricitySource",
    "EIANaturalGasSource",
    "EIAPetroleumSource",
    "EIASTEOSource",
    "PlattsSource",
    "IRENASource",
    "EmberEnergySource",
    # Tier 1: Shipping/Transport (3)
    "FreightosSource",
    "PortCongestionSource",
    "AISStreamSource",
    # Prediction Markets
    "PolymarketSource",
    "KalshiSource",
]
