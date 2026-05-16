"""Application configuration with frozen immutability constraints."""

import tomllib
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field


class ThresholdSettings(BaseModel):
    """Thresholds for analysis engines."""

    model_config = ConfigDict(frozen=True)  # H-4: Prevent threshold mutations

    locality_window: int = Field(10, ge=1, description="Sliding window size for locality scoring")
    thrash_repeat_limit: int = Field(3, ge=2, description="Min revisits to flag thrashing")
    churn_ratio_limit: float = Field(0.4, ge=0.0, le=1.0, description="Max acceptable churn ratio")
    waste_gap_seconds: float = Field(30.0, ge=0.0, description="Min idle gap to count as waste")


class Settings(BaseModel):
    """Top-level application settings."""

    model_config = ConfigDict(frozen=True)  # H-4: Ensure global settings instance is read-only

    app_name: str = "LocalityLens"
    version: str = "0.1.0"
    log_level: str = "INFO"
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from an optional localitylens.toml file."""
        config_path = Path("localitylens.toml")
        if not config_path.is_file():
            return cls()

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
            return cls(**data)
        except Exception:
            return cls()


# Singleton instance used throughout the application.
settings = Settings.load()