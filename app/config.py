"""Application configuration for the risk estimator service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final, List

from pydantic import BaseSettings, validator

# Default microservice names to simulate within the dependency graph.
DEFAULT_SERVICE_NAMES: Final[List[str]] = [
    "auth-service",
    "payment-service",
    "inventory-service",
    "email-service",
    "orders-service",
    "analytics-service",
    "search-service",
    "notification-service",
    "reporting-service",
    "billing-service",
]

# Static list of candidate dependencies for each service. The risk engine
# will choose a subset per simulation to keep the graph varied while grounded
# in realistic service relationships.
DEFAULT_DEPENDENCY_CANDIDATES: Final[dict[str, list[str]]] = {
    "auth-service": ["orders-service", "payment-service", "notification-service"],
    "payment-service": ["billing-service", "orders-service"],
    "inventory-service": ["orders-service", "analytics-service"],
    "email-service": ["notification-service"],
    "orders-service": ["inventory-service", "payment-service", "analytics-service"],
    "analytics-service": ["reporting-service", "search-service"],
    "search-service": ["analytics-service"],
    "notification-service": ["email-service"],
    "reporting-service": ["analytics-service", "billing-service"],
    "billing-service": ["payment-service", "reporting-service"],
}


class Settings(BaseSettings):
    """Strongly typed application settings sourced from environment variables."""

    service_names: List[str] = DEFAULT_SERVICE_NAMES
    dependency_candidates: dict[str, list[str]] = DEFAULT_DEPENDENCY_CANDIDATES
    history_limit: int = 5
    export_directory: Path = Path("exports")
    graph_image_path: Path = Path("graph.png")
    barchart_image_path: Path = Path("barchart.png")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("history_limit")
    def _validate_history_limit(cls, value: int) -> int:
        """Ensure that the rolling history limit remains within sensible bounds."""
        if value < 1:
            raise ValueError("history_limit must be at least 1")
        if value > 20:
            raise ValueError("history_limit must not exceed 20")
        return value

    @validator("export_directory", pre=True)
    def _coerce_export_directory(cls, value: Path | str) -> Path:
        """Normalise export directory to a Path instance."""
        return Path(value)


@lru_cache()
def get_settings() -> Settings:
    """Cache and return application settings for reuse."""
    return Settings()


