"""Application-wide configuration with dynamic TOML loading."""

import tomllib
from pathlib import Path
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

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from an optional localitylens.toml file in the current working directory."""
        config_path = Path("localitylens.toml")
        if not config_path.is_file():
            return cls()

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
            # Pydantic v2 automatically uses defaults for any missing nested keys
            return cls(**data)
        except Exception:
            # Gracefully fall back to internal defaults if parsing or validation fails
            return cls()


# Singleton instance used throughout the application.
settings = Settings.load()