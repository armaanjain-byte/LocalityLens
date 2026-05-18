"""Unit tests for trace file parsers."""

from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from localitylens.core.exceptions import ParseError
from localitylens.core.trace import EventKind, TraceFormat
from localitylens.parsers.claude_code import ClaudeCodeParser
from localitylens.parsers.generic_json import GenericJsonParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# ClaudeCodeParser
# ---------------------------------------------------------------------------

class TestClaudeCodeParser:
    def test_can_parse_jsonl(self, tmp_path):
        p = _write(tmp_path, "trace.jsonl", "")
        assert ClaudeCodeParser().can_parse(p) is True

    def test_cannot_parse_json(self, tmp_path):
        p = _write(tmp_path, "trace.json", "")
        assert ClaudeCodeParser().can_parse(p) is False

    def test_parses_tool_use_read(self, tmp_path):
        line = json.dumps({
            "type": "tool_use",
            "name": "read_file",
            "timestamp": "2026-01-01T00:00:00Z",
            "input": {"path": "src/main.py"},
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        assert len(trace.events) == 1
        assert trace.events[0].kind == EventKind.FILE_READ
        assert trace.events[0].target == "src/main.py"

    def test_parses_tool_use_str_replace_as_write(self, tmp_path):
        line = json.dumps({
            "type": "tool_use",
            "name": "str_replace",
            "timestamp": "2026-01-01T00:00:00Z",
            "input": {"path": "src/a.py"},
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        assert trace.events[0].kind == EventKind.FILE_WRITE

    def test_parses_assistant_message_as_llm_turn(self, tmp_path):
        line = json.dumps({
            "type": "message",
            "role": "assistant",
            "timestamp": "2026-01-01T00:00:00Z",
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        assert trace.events[0].kind == EventKind.LLM_TURN
        assert trace.events[0].target == "llm"

    def test_skips_malformed_json_lines(self, tmp_path):
        content = textwrap.dedent("""\
            {this is not json}
            {"type": "tool_use", "name": "read_file", "timestamp": "2026-01-01T00:00:00Z", "input": {"path": "a.py"}}
        """)
        p = _write(tmp_path, "trace.jsonl", content)
        trace = ClaudeCodeParser().parse(p)
        assert len(trace.events) == 1  # bad line skipped, good line parsed

    def test_empty_file_raises_parse_error(self, tmp_path):
        p = _write(tmp_path, "trace.jsonl", "")
        with pytest.raises(ParseError, match="No parseable events"):
            ClaudeCodeParser().parse(p)

    def test_missing_timestamp_defaults_to_epoch(self, tmp_path):
        line = json.dumps({
            "type": "tool_use",
            "name": "read_file",
            "input": {"path": "a.py"},
            # no "timestamp" key
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        assert trace.events[0].timestamp == epoch

    def test_null_input_field_handled(self, tmp_path):
        """input: null must not raise — target falls back to tool name."""
        line = json.dumps({
            "type": "tool_use",
            "name": "bash",
            "timestamp": "2026-01-01T00:00:00Z",
            "input": None,
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        assert trace.events[0].target == "bash"

    def test_trace_format_is_claude_code(self, tmp_path):
        line = json.dumps({
            "type": "tool_use",
            "name": "read_file",
            "timestamp": "2026-01-01T00:00:00Z",
            "input": {"path": "a.py"},
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        trace = ClaudeCodeParser().parse(p)
        assert trace.format == TraceFormat.CLAUDE_CODE
        assert trace.agent == "claude-code"

    def test_trace_id_is_stable_for_same_file(self, tmp_path):
        line = json.dumps({
            "type": "tool_use",
            "name": "read_file",
            "timestamp": "2026-01-01T00:00:00Z",
            "input": {"path": "a.py"},
        })
        p = _write(tmp_path, "trace.jsonl", line + "\n")
        t1 = ClaudeCodeParser().parse(p)
        t2 = ClaudeCodeParser().parse(p)
        assert t1.trace_id == t2.trace_id


# ---------------------------------------------------------------------------
# GenericJsonParser
# ---------------------------------------------------------------------------

class TestGenericJsonParser:
    def test_can_parse_json(self, tmp_path):
        p = _write(tmp_path, "trace.json", "[]")
        assert GenericJsonParser().can_parse(p) is True

    def test_cannot_parse_jsonl(self, tmp_path):
        p = _write(tmp_path, "trace.jsonl", "")
        assert GenericJsonParser().can_parse(p) is False

    def test_parses_valid_event_array(self, tmp_path):
        data = [{"kind": "file_read", "timestamp": "2026-01-01T00:00:00Z", "target": "a.py"}]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        assert len(trace.events) == 1
        assert trace.events[0].kind == EventKind.FILE_READ
        assert trace.events[0].target == "a.py"

    def test_non_array_root_raises_parse_error(self, tmp_path):
        p = _write(tmp_path, "trace.json", json.dumps({"key": "value"}))
        with pytest.raises(ParseError, match="Expected a JSON array"):
            GenericJsonParser().parse(p)

    def test_empty_array_raises_parse_error(self, tmp_path):
        p = _write(tmp_path, "trace.json", "[]")
        with pytest.raises(ParseError, match="No events found"):
            GenericJsonParser().parse(p)

    def test_missing_target_skips_event(self, tmp_path):
        data = [
            {"kind": "file_read", "timestamp": "2026-01-01T00:00:00Z", "target": ""},
            {"kind": "file_read", "timestamp": "2026-01-01T00:00:00Z", "target": "b.py"},
        ]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        assert len(trace.events) == 1
        assert trace.events[0].target == "b.py"

    def test_unknown_kind_defaults_to_unknown(self, tmp_path):
        data = [{"kind": "completely_made_up", "timestamp": "2026-01-01T00:00:00Z", "target": "a.py"}]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        assert trace.events[0].kind == EventKind.UNKNOWN

    def test_missing_timestamp_defaults_to_epoch(self, tmp_path):
        data = [{"kind": "file_read", "target": "a.py"}]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        assert trace.events[0].timestamp == epoch

    def test_skips_non_object_elements(self, tmp_path):
        data = ["not_an_object", {"kind": "file_read", "timestamp": "2026-01-01T00:00:00Z", "target": "a.py"}]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        assert len(trace.events) == 1

    def test_trace_format_is_generic_json(self, tmp_path):
        data = [{"kind": "file_read", "timestamp": "2026-01-01T00:00:00Z", "target": "a.py"}]
        p = _write(tmp_path, "trace.json", json.dumps(data))
        trace = GenericJsonParser().parse(p)
        assert trace.format == TraceFormat.GENERIC_JSON