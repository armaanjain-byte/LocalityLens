"""Unit tests for target filtering helpers."""

from __future__ import annotations

from localitylens.utils.filters import is_real_file_target


def test_filter_rejects_tool_names_and_commands():
    assert not is_real_file_target("bash")
    assert not is_real_file_target("grep")
    assert not is_real_file_target("ls -la src/")


def test_filter_accepts_file_like_targets():
    assert is_real_file_target("main.py")
    assert is_real_file_target("src/localitylens/analysis/anomaly.py")
