"""Application-wide configuration via pydantic with upward TOML traversal loading."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pydantic
from pydantic import BaseModel, ConfigDict, Field


class ThresholdSettings(BaseModel):
    """Thresholds for analysis engines."""

    model_config = ConfigDict(frozen=True)

    locality_window: int = Field(10, ge=1, description="Sliding window size for locality scoring")
    thrash_repeat_limit: int = Field(3, ge=2, description="Min revisits to flag thrashing")
    churn_ratio_limit: float = Field(0.4, ge=0.0, le=1.0, description="Max acceptable churn ratio")
    waste_gap_seconds: float = Field(30.0, ge=0.0, description="Min idle gap to count as waste")


class Settings(BaseModel):
    """Top-level application settings."""

    model_config = ConfigDict(frozen=True)

    app_name: str = "LocalityLens"
    version: str = "0.1.0"
    log_level: str = "INFO"
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        """Load settings; searches upward from CWD for a localitylens.toml file.

        Raises:
            ValueError: When a config file is found but contains invalid TOML
                        or fails pydantic validation.  This surfaces
                        configuration mistakes instead of silently ignoring them.
        """
        if config_path is None:
            cwd = Path.cwd()
            for parent in [cwd, *cwd.parents]:
                candidate = parent / "localitylens.toml"
                if candidate.is_file():
                    config_path = candidate
                    break

        if config_path is None or not config_path.is_file():
            return cls()

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid TOML in {config_path}: {exc}") from exc

        try:
            return cls(**data)
        except pydantic.ValidationError as exc:
            raise ValueError(
                f"Invalid settings in {config_path}:\n{exc}"
            ) from exc


# Singleton instance used throughout the application.
settings = Settings.load()