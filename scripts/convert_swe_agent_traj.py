import json
import re
import random
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from localitylens.semantic.session_state import SessionState

INPUT_FILE = "data/raw/train-00000-of-00012.parquet"
OUTPUT_FILE = "data/processed/normalized_trace.json"


READ_PATTERNS = [
    r"open\s+([^\s]+)",
    r"cat\s+([^\s]+)",
    r"search_file\s+[^\s]+\s+([^\s]+)",
    r"find_file\s+([^\s]+)",
]

WRITE_PATTERNS = [
    r"edit\s+([0-9]+):([0-9]+)",
    r"create\s+([^\s]+)",
]

SEARCH_PATTERNS = [
    r"search_dir\s+([^\s]+)",
    r"search_file\s+([^\s]+)",
    r"find_file\s+([^\s]+)",
]


def extract_commands(text: str):
    if not text:
        return []

    commands = []

    for line in text.splitlines():
        line = line.strip()

        if (
            line.startswith("open ")
            or line.startswith("cat ")
            or line.startswith("edit ")
            or line.startswith("create ")
            or line.startswith("search_file ")
            or line.startswith("search_dir ")
            or line.startswith("find_file ")
            or line.startswith("submit")
        ):
            commands.append(line)

    return commands

def extract_event(command: str, state: SessionState):
    command = command.strip()

    if command.startswith("open "):
        parts = command.split(maxsplit=1)

        if len(parts) > 1:
            target = parts[1].split()[0]

            state.set_current_file(target)

            return {
                "event_type": "file_read",
                "target": target,
            }

    if command.startswith("cat "):
        parts = command.split(maxsplit=1)

        if len(parts) > 1:
            target = parts[1]

            state.set_current_file(target)

            return {
                "event_type": "file_read",
                "target": target,
            }

    if command.startswith("edit "):
        current = state.get_current_file()

        return {
            "event_type": "file_write",
            "target": current or "unknown_file",
        }

    if command.startswith("create "):
        parts = command.split(maxsplit=1)

        if len(parts) > 1:
            target = parts[1]

            state.set_current_file(target)

            return {
                "event_type": "file_write",
                "target": target,
            }

    if (
        command.startswith("search_file ")
        or command.startswith("search_dir ")
        or command.startswith("find_file ")
    ):
        return {
            "event_type": "search",
            "target": command,
            "metadata": {
                "query": command,
            },
        }

    if command.startswith("submit"):
        return {
            "event_type": "submit",
            "target": "session",
        }

    return None

def main():
    random.seed(42)
    print(f"Loading parquet: {INPUT_FILE}")

    df = pd.read_parquet(INPUT_FILE)

    normalized_events = []
    current_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for row in df.to_dict("records"):
        state = SessionState()
        instance_id = row["instance_id"]
        trajectory = row["trajectory"]

        for step_index, step in enumerate(trajectory):
            text = step.get("text")

            commands = extract_commands(text)

            for command in commands:
                event = extract_event(command, state)

                if not event:
                    continue

                if event["event_type"] == "file_read":
                    delta = random.randint(1, 3)
                elif event["event_type"] == "file_write":
                    delta = random.randint(5, 15)

                elif event["event_type"] == "search":
                    delta = random.randint(2, 6)

                elif event["event_type"] == "submit":
                    delta = random.randint(1, 2)

                else:
                    delta = random.randint(1, 4)

                if random.random() < 0.03:
                    delta += random.randint(30, 90)


                current_time += timedelta(seconds=delta)

                normalized_event = {
                    "metadata": event.get("metadata", {}),
                    "timestamp": current_time.isoformat(),
                    "instance_id": instance_id,
                    "source": "swe-agent",
                    "kind": event["event_type"],
                    "target": event["target"],
                    "role": step.get("role"),
                }

                normalized_events.append(normalized_event)

    Path("data/processed").mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized_events, f, indent=2)

    print(f"\nGenerated {len(normalized_events)} normalized events")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
