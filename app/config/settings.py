from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TargetMarket:
    city: str = "Milan"
    country: str = "Italy"
    remote_preference: str = "Remote / Hybrid in Italy"
    office_frequency: str = "Hybrid, 2-3 days/week when applicable"


@dataclass(frozen=True)
class RolePriority:
    title: str
    priority: str


TARGET_MARKET = TargetMarket()
ROLE_PRIORITIES = (
    RolePriority("Data Engineer", "Tier 1"),
    RolePriority("ETL Developer", "Tier 1"),
    RolePriority("Data Platform Engineer", "Tier 1"),
    RolePriority("Analytics Engineer", "Tier 1"),
    RolePriority("Data Warehouse Engineer", "Tier 1"),
    RolePriority("AI Engineer", "Tier 1"),
    RolePriority("BI Engineer", "Tier 2"),
    RolePriority("Data Analyst", "Tier 2"),
)
