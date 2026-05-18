"""Malformed-input integration coverage for parser and pipeline boundaries."""

from __future__ import annotations

import json

import pytest

from localitylens.core.exceptions import ParseError, UnsupportedFormatError
from localitylens.pipeline import parse_trace, run_pipeline


def test_invalid_json_array_fails_cleanly(tmp_path):
    trace_file = tmp_path / "broken.json"
    trace_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ParseError):
        run_pipeline(trace_file)


def test_claude_jsonl_skips_bad_lines_but_keeps_valid_events(tmp_path):
    trace_file = tmp_path / "trace.jsonl"
    valid = {
        "type": "tool_use",
        "name": "read_file",
        "timestamp": "2026-05-16T12:00:00Z",
        "input": {"path": "src/a.py"},
    }
    trace_file.write_text("{bad json\n" + json.dumps(valid) + "\n", encoding="utf-8")

    trace = parse_trace(trace_file)

    assert len(trace.events) == 1
    assert trace.events[0].target == "src/a.py"


def test_parser_mismatch_raises_unsupported_format(tmp_path):
    trace_file = tmp_path / "trace.txt"
    trace_file.write_text("[]", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError):
        run_pipeline(trace_file)
