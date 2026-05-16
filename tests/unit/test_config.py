"""Unit tests for the dynamic configuration loading system."""

from pathlib import Path
from localitylens.config.settings import Settings


def test_settings_fallback_to_defaults():
    """Ensure system falls back to default constants when no file exists."""
    # Ensure any temporary test configuration file is absent
    test_file = Path("localitylens.toml")
    if test_file.is_file():
        test_file.unlink()

    loaded_settings = Settings.load()
    assert loaded_settings.log_level == "INFO"
    assert loaded_settings.thresholds.thrash_repeat_limit == 3


def test_settings_override_via_toml():
    """Ensure local TOML configurations successfully override application fields."""
    test_file = Path("localitylens.toml")
    
    # Write a temporary override profile
    toml_content = """
    log_level = "DEBUG"

    [thresholds]
    thrash_repeat_limit = 5
    """
    test_file.write_text(toml_content, encoding="utf-8")

    try:
        loaded_settings = Settings.load()
        assert loaded_settings.log_level == "DEBUG"
        # Overridden field
        assert loaded_settings.thresholds.thrash_repeat_limit == 5
        # Verifying unmentioned nested keys still smoothly inherited standard system defaults
        assert loaded_settings.thresholds.locality_window == 10
    finally:
        # Clean up filesystem side-effects completely
        if test_file.is_file():
            test_file.unlink()