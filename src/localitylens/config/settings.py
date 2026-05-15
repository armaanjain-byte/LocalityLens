"""Application-wide configuration via pydantic-settings."""

from pydantic import BaseModel, Field


class ThresholdSettings(BaseModel):
    """Thresholds for analysis engines."""

    locality_window: int = Field(10, ge=1, description="Sliding window size for locality scoring")
    thrash_repeat_limit: int = Field(3, ge=2, description="Min revisits to flag thrashing")
    churn_ratio_limit: float = Field(0.4, ge=0.0, le=1.0, description="Max acceptable churn ratio")
    waste_gap_seconds: float = Field(30.0, ge=0.0, description="Min idle gap to count as waste")


class Settings(BaseModel):
    """Top-level application settings."""

    app_name: str = "LocalityLens"
    version: str = "0.1.0"
    log_level: str = "INFO"
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)


# Singleton instance used throughout the application.
settings = Settings()