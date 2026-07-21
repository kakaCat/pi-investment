"""WEForum (World Economic Forum) geopolitical risk data source.

Provides World Economic Forum reports and geopolitical risk analysis:
- Global Risks Report (annual survey of top global risks)
- Risk categories (economic, environmental, geopolitical, societal, technological)
- Risk scores and trend data
- Geopolitical risk interconnections

No API key required (public data).

Risk data sourced from: https://www.weforum.org/reports/global-risks-report
Embedded reference data provides risk framework even without API access.
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WEForumSource(EconomicDataSource):
    """World Economic Forum data source.

    Provides access to:
    - Global Competitiveness Report
    - Global Risks Report
    - Future of Jobs Report
    - Global Gender Gap Report
    - Travel & Tourism Competitiveness
    - Energy Transition Index
    - Sustainable Development Impact

    No API key required (public data).
    """

    BASE_URL = "https://www.weforum.org"
    REPORTS_URL = "https://www.weforum.org/reports"

    # Major report types
    REPORTS = {
        "competitiveness": "Global Competitiveness Report",
        "risks": "Global Risks Report",
        "jobs": "Future of Jobs Report",
        "gender_gap": "Global Gender Gap Report",
        "travel_tourism": "Travel & Tourism Competitiveness Report",
        "energy_transition": "Energy Transition Index",
        "digital_competitiveness": "Global Digital Competitiveness Report"
    }

    def __init__(self):
        """Initialize WEForum data source."""
        super().__init__(name="WEForum", requires_api_key=False)
        self.session = SessionManager.get_session("weforum")

        self.RISK_CATEGORIES = {
            "economic": {
                "name": "Economic Risks",
                "examples": [
                    "Asset bubble burst", "Debt crisis", "Commodity price shocks",
                    "Economic downturn", "Inflation crisis", "Supply chain disruption",
                    "Critical infrastructure failure",
                ],
                "investor_impact": "Direct impact on valuations, currencies, trade flows",
                "time_horizon": "Short-term (0-2 years)",
            },
            "environmental": {
                "name": "Environmental Risks",
                "examples": [
                    "Climate action failure", "Extreme weather events",
                    "Biodiversity loss", "Natural disasters",
                    "Natural resource crises", "Pollution crisis",
                ],
                "investor_impact": "Long-term structural risks to agriculture, insurance, real estate",
                "time_horizon": "Long-term (5-10 years)",
            },
            "geopolitical": {
                "name": "Geopolitical Risks",
                "examples": [
                    "Interstate conflict", "Terrorism", "Weapons of mass destruction",
                    "State collapse", "Geoeconomic confrontation",
                    "Strategic resource competition",
                ],
                "investor_impact": "Market volatility, sanctions, trade route disruption, capital flight",
                "time_horizon": "Medium-term (2-5 years)",
            },
            "societal": {
                "name": "Societal Risks",
                "examples": [
                    "Cost-of-living crisis", "Social cohesion erosion",
                    "Infectious diseases", "Mental health deterioration",
                    "Involuntary migration", "Social security collapse",
                ],
                "investor_impact": "Labor market instability, consumer spending shifts",
                "time_horizon": "Medium-term (2-5 years)",
            },
            "technological": {
                "name": "Technological Risks",
                "examples": [
                    "Adverse AI outcomes", "Cybersecurity failures",
                    "Digital power concentration", "Digital inequality",
                    "Critical information infrastructure breakdown",
                ],
                "investor_impact": "Sector disruption, regulatory shifts, security premium",
                "time_horizon": "Medium-term (2-5 years)",
            },
        }

        self._GEO_SEVERE_PATTERNS = [
            re.compile(p, re.IGNORECASE) for p in [
                r"\b(?:war|invasion|airstrike|military\s+attack|declared?\s+war)\b",
                r"\b(?:martial\s+law|coup|civil\s+war)\b",
                r"\b(?:terrorist\s+attack|nuclear\s+(?:strike|threat))\b",
            ]
        ]
        self._GEO_MODERATE_PATTERNS = [
            re.compile(p, re.IGNORECASE) for p in [
                r"\bgeopolitical\b",
                r"\b(?:armed|military)\s+conflict\b",
                r"\bsanctions?\s+(?:on|against)\b",
                r"\b(?:trade\s+war|tariff\s+war)\b",
                r"\b(?:border\s+tension|territorial\s+dispute)\b",
                r"\b(?:supply\s+chain\s+diversion|decoupling)\b",
            ]
        ]

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to WEForum website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "WEForum"},
                metadata={"source": "WEForum", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"WEForum connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_report_types(self) -> DataSourceResponse:
        """Get list of major report types.

        Returns:
            DataSourceResponse with report types
        """
        reports = [
            {"key": key, "name": name}
            for key, name in self.REPORTS.items()
        ]

        return DataSourceResponse.success_response(
            data=reports,
            metadata={
                "source": "WEForum",
                "count": len(reports)
            }
        )

    def get_reports(self) -> DataSourceResponse:
        """Get reports page information.

        Returns:
            DataSourceResponse with reports page info
        """
        try:
            response = self.session.get(
                self.REPORTS_URL,
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": self.REPORTS_URL,
                    "note": "HTML parsing required for report list"
                },
                metadata={
                    "source": "WEForum",
                    "data_type": "reports"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_reports")

    def get_competitiveness_report(self) -> DataSourceResponse:
        """Get Global Competitiveness Report information.

        Returns:
            DataSourceResponse with report info
        """
        try:
            response = self.session.get(
                f"{self.REPORTS_URL}/global-competitiveness-report",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.REPORTS_URL}/global-competitiveness-report",
                    "report": "Global Competitiveness Report",
                    "description": "Annual assessment of national competitiveness",
                    "note": "HTML parsing or PDF download required for data"
                },
                metadata={
                    "source": "WEForum",
                    "report_type": "competitiveness"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_competitiveness_report")

    def get_risks_report(self) -> DataSourceResponse:
        """Get Global Risks Report information.

        Returns:
            DataSourceResponse with report info
        """
        try:
            response = self.session.get(
                f"{self.REPORTS_URL}/global-risks-report",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.REPORTS_URL}/global-risks-report",
                    "report": "Global Risks Report",
                    "description": "Annual assessment of global risks",
                    "note": "HTML parsing or PDF download required for data"
                },
                metadata={
                    "source": "WEForum",
                    "report_type": "risks"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_risks_report")

    def get_jobs_report(self) -> DataSourceResponse:
        """Get Future of Jobs Report information.

        Returns:
            DataSourceResponse with report info
        """
        try:
            response = self.session.get(
                f"{self.REPORTS_URL}/future-of-jobs-report",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.REPORTS_URL}/future-of-jobs-report",
                    "report": "Future of Jobs Report",
                    "description": "Labor market trends and future skills",
                    "note": "HTML parsing or PDF download required for data"
                },
                metadata={
                    "source": "WEForum",
                    "report_type": "jobs"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_jobs_report")

    def get_gender_gap_report(self) -> DataSourceResponse:
        """Get Global Gender Gap Report information.

        Returns:
            DataSourceResponse with report info
        """
        try:
            response = self.session.get(
                f"{self.REPORTS_URL}/global-gender-gap-report",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.REPORTS_URL}/global-gender-gap-report",
                    "report": "Global Gender Gap Report",
                    "description": "Gender parity across countries",
                    "note": "HTML parsing or PDF download required for data"
                },
                metadata={
                    "source": "WEForum",
                    "report_type": "gender_gap"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_gender_gap_report")

    def get_energy_transition_index(self) -> DataSourceResponse:
        """Get Energy Transition Index information.

        Returns:
            DataSourceResponse with index info
        """
        try:
            response = self.session.get(
                f"{self.REPORTS_URL}/energy-transition-index",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.REPORTS_URL}/energy-transition-index",
                    "report": "Energy Transition Index",
                    "description": "Country readiness for energy transition",
                    "note": "HTML parsing or PDF download required for data"
                },
                metadata={
                    "source": "WEForum",
                    "report_type": "energy_transition"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_energy_transition_index")

    # --- Inherited abstract methods ---

    def get_series(self, series_id: str, start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> DataSourceResponse:
        return self.get_risk_category(series_id)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        return self.search_risks(query, limit)

    # --- Geopolitical risk methods ---

    def get_risk_categories(self) -> DataSourceResponse:
        """Get all risk categories with example risks."""
        categories = [
            {"id": k, **{k2: v2 for k2, v2 in v.items() if k2 != "examples"},
             "example_risks": v["examples"]}
            for k, v in self.RISK_CATEGORIES.items()
        ]
        return DataSourceResponse.success_response(
            data=categories,
            metadata={"source": "WEForum", "count": len(categories),
                      "timestamp": datetime.utcnow().isoformat()}
        )

    def get_risk_category(self, category: str) -> DataSourceResponse:
        """Get a specific risk category with its example risks.

        Args:
            category: One of: economic, environmental, geopolitical, societal, technological
        """
        cat = self.RISK_CATEGORIES.get(category.lower())
        if not cat:
            valid = list(self.RISK_CATEGORIES.keys())
            return DataSourceResponse.error_response(
                error=f"Unknown category '{category}'. Available: {valid}"
            )
        return DataSourceResponse.success_response(
            data={"category": category, **cat},
            metadata={"source": "WEForum", "category": category}
        )

    def get_top_risks(self, category: Optional[str] = None, n: int = 10) -> DataSourceResponse:
        """Get top global risks.

        Args:
            category: Filter by category (optional). One of: economic,
                     environmental, geopolitical, societal, technological
            n: Number of top risks to return
        """
        if category:
            cat_data = self.RISK_CATEGORIES.get(category.lower())
            if not cat_data:
                return DataSourceResponse.error_response(
                    error=f"Unknown category '{category}'"
                )
            risks = [
                {"risk": r, "category": category, "impact": cat_data["investor_impact"],
                 "horizon": cat_data["time_horizon"]}
                for r in cat_data["examples"][:n]
            ]
        else:
            risks = []
            for cat_key, cat_data in self.RISK_CATEGORIES.items():
                for risk in cat_data["examples"][:3]:
                    risks.append({
                        "risk": risk, "category": cat_key,
                        "impact": cat_data["investor_impact"],
                        "horizon": cat_data["time_horizon"],
                    })
            risks = risks[:n]

        return DataSourceResponse.success_response(
            data=risks,
            metadata={"source": "WEForum", "category": category or "all",
                      "count": len(risks), "timestamp": datetime.utcnow().isoformat()}
        )

    def search_risks(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search across all risk categories for matching risks.

        Args:
            query: Search keyword
            limit: Max results
        """
        query_lower = query.lower()
        results = []
        for cat_key, cat_data in self.RISK_CATEGORIES.items():
            for risk in cat_data["examples"]:
                if query_lower in risk.lower() or query_lower in cat_data["name"].lower():
                    results.append({
                        "risk": risk, "category": cat_key,
                        "impact": cat_data["investor_impact"],
                        "horizon": cat_data["time_horizon"],
                    })
        results = results[:limit]

        return DataSourceResponse.success_response(
            data=results,
            metadata={"source": "WEForum", "query": query, "count": len(results)}
        )

    def analyze_geopolitical_risk(self, text: str) -> DataSourceResponse:
        """Analyze text for geopolitical risk severity.

        Detects mentions of war, conflict, sanctions, trade wars, etc.
        and returns a risk assessment.

        Args:
            text: News article text, headline, or any text to analyze

        Returns:
            DataSourceResponse with risk level (severe/moderate/low) and matched patterns
        """
        severe_matches = []
        moderate_matches = []

        for pattern in self._GEO_SEVERE_PATTERNS:
            matches = pattern.findall(text)
            severe_matches.extend(matches)

        for pattern in self._GEO_MODERATE_PATTERNS:
            matches = pattern.findall(text)
            moderate_matches.extend(matches)

        if severe_matches:
            level = "severe"
            sentiment_penalty = -42
            description = "Critical geopolitical event detected - major market impact expected"
        elif moderate_matches:
            level = "moderate"
            sentiment_penalty = -18
            description = "Geopolitical tension detected - moderate market impact possible"
        else:
            level = "low"
            sentiment_penalty = 0
            description = "No significant geopolitical risk detected"

        return DataSourceResponse.success_response(
            data={
                "risk_level": level,
                "sentiment_penalty": sentiment_penalty,
                "description": description,
                "severe_matches": list(set(severe_matches)) if severe_matches else [],
                "moderate_matches": list(set(moderate_matches)) if moderate_matches else [],
            },
            metadata={"source": "WEForum", "analysis_type": "geopolitical_risk",
                      "text_length": len(text)}
        )

    def get_geopolitical_risk_overview(self) -> DataSourceResponse:
        """Get comprehensive geopolitical risk overview for investment analysis.

        Returns all geopolitical risks with investor impact assessment.
        """
        geo_cat = self.RISK_CATEGORIES["geopolitical"]
        economic_cat = self.RISK_CATEGORIES["economic"]

        return DataSourceResponse.success_response(
            data={
                "geopolitical_risks": geo_cat["examples"],
                "economic_risks_related": [
                    r for r in economic_cat["examples"]
                    if any(kw in r.lower() for kw in ["sanction", "trade", "supply", "conflict"])
                ],
                "investor_guidance": {
                    "severe_events": {
                        "impact": "Market circuit breaker risk, capital controls possible",
                        "sectors_affected": ["Energy", "Defense", "Airlines", "Shipping"],
                        "hedging": ["Gold", "US Treasuries", "VIX derivatives", "Safe-haven currencies"],
                    },
                    "moderate_events": {
                        "impact": "Sector rotation, risk premium expansion",
                        "sectors_affected": ["Semiconductors", "Rare earths", "Defense"],
                        "hedging": ["Defense sector ETFs", "Diversified supply chain baskets"],
                    },
                    "low_tension": {
                        "impact": "Business-as-usual with monitoring",
                        "monitoring_indicators": ["DXY", "VIX", "TNX", "CDS spreads", "Shipping indices"],
                    },
                },
                "detection_capability": {
                    "severe_patterns": [p.pattern for p in self._GEO_SEVERE_PATTERNS],
                    "moderate_patterns": [p.pattern for p in self._GEO_MODERATE_PATTERNS],
                },
            },
            metadata={"source": "WEForum", "analysis_type": "geopolitical_overview",
                      "timestamp": datetime.utcnow().isoformat()}
        )

    def get_agenda(self) -> DataSourceResponse:
        """Get WEForum agenda and articles.

        Returns:
            DataSourceResponse with agenda info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/agenda",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/agenda",
                    "description": "WEForum articles and insights",
                    "note": "HTML parsing required for article list"
                },
                metadata={
                    "source": "WEForum",
                    "data_type": "agenda"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WEForum", "get_agenda")
