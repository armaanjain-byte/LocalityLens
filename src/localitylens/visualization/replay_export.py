import json


class ReplayExporter:
    """
    Export temporal transition frames for replay visualization.
    """

    def export(
        self,
        trace,
        output_path="replay_frames.json",
    ):
        frames = []

        previous = None

        for idx, event in enumerate(trace.events):

            target = getattr(event, "target", None)

            if not target:
                continue

            if previous is not None:
                timestamp = getattr(event, "timestamp", idx)

                if hasattr(timestamp, "isoformat"):
                 timestamp = timestamp.isoformat()
                frame = {
                    "step": idx,
                    "timestamp": timestamp,
                    "from": previous,
                    "to": target,
                    "event_type": event.kind.value,
                }

                frames.append(frame)

            previous = target

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(frames, f, indent=2)

        return output_path