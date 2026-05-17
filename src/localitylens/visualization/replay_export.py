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
                raw_timestamp = getattr(event, "timestamp", idx)

                timestamp = (
                raw_timestamp.isoformat()
                if hasattr(raw_timestamp, "isoformat")
                else raw_timestamp
               )

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