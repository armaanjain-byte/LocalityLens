"""Unit tests for the dynamic configuration loading system."""

from localitylens.config.settings import Settings, get_settings


def test_settings_fallback_to_defaults(tmp_path):
    """Ensure system falls back to default constants when no file exists."""
    loaded_settings = Settings.load(config_path=tmp_path / "missing.toml")
    assert loaded_settings.log_level == "INFO"
    assert loaded_settings.thresholds.thrash_repeat_limit == 3


def test_settings_override_via_toml(tmp_path):
    """Ensure local TOML configurations successfully override application fields."""
    test_file = tmp_path / "localitylens.toml"
    
    # Write a temporary override profile
    toml_content = """
    log_level = "DEBUG"

    [thresholds]
    thrash_repeat_limit = 5
    """
    test_file.write_text(toml_content, encoding="utf-8")

    loaded_settings = Settings.load(config_path=test_file)
    assert loaded_settings.log_level == "DEBUG"
    assert loaded_settings.thresholds.thrash_repeat_limit == 5
    assert loaded_settings.thresholds.locality_window == 10


def test_get_settings_returns_fresh_values(tmp_path):
    first = tmp_path / "first.toml"
    second = tmp_path / "second.toml"
    first.write_text("log_level = \"DEBUG\"\n", encoding="utf-8")
    second.write_text("log_level = \"WARNING\"\n", encoding="utf-8")

    assert get_settings(first).log_level == "DEBUG"
    assert get_settings(second).log_level == "WARNING"
