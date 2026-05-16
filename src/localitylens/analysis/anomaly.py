from collections import Counter, deque

from localitylens.core.metrics import Severity
from localitylens.core.metrics import MetricResult

class AnomalyAnalyzer:
    """
    Detect behavioral instability patterns in agent traces.
    """

    def analyze(self, trace, report):

        anomalies = []

        recent = deque(maxlen=25)

        revisit_counter = Counter()

        previous = None
        oscillation_count = 0

        for idx, event in enumerate(trace.events):

            target = getattr(event, "target", None)

            if not target:
                continue

            # -----------------------------------------
            # Revisit pressure
            # -----------------------------------------

            revisit_counter[target] += 1

            if revisit_counter[target] in (15, 30, 60):

                anomalies.append({
                    "step": idx,
                    "severity": "CRITICAL",
                    "type": "hotspot_revisit",
                    "message":
                        f"{target} revisited "
                        f"{revisit_counter[target]} times"
                })

            # -----------------------------------------
            # Oscillation loops
            # -----------------------------------------

            recent.append(target)

            if len(recent) >= 4:

                last_four = list(recent)[-4:]

                a, b, c, d = last_four

                if a == c and b == d and a != b:

                    oscillation_count += 1

                    anomalies.append({
                        "step": idx,
                        "severity": "WARNING",
                        "type": "oscillation",
                        "message":
                            f"Oscillation between "
                            f"{a} <-> {b}"
                    })

            # -----------------------------------------
            # Semantic jump bursts
            # -----------------------------------------

            if previous and previous != target:

                prev_root = previous.split("/")[0]
                curr_root = target.split("/")[0]

                if prev_root != curr_root:

                    anomalies.append({
                        "step": idx,
                        "severity": "LOW",
                        "type": "semantic_jump",
                        "message":
                            f"{previous} -> {target}"
                    })

            previous = target

        # -------------------------------------------------
        # Aggregate Metrics
        # -------------------------------------------------

        criticals = sum(
            1 for a in anomalies
            if a["severity"] == "CRITICAL"
        )

        warnings = sum(
            1 for a in anomalies
            if a["severity"] == "WARNING"
        )

        score = criticals * 3 + warnings

        if score > 25:
            severity = Severity.CRITICAL

        elif score > 10:
            severity = Severity.WARNING

        else:
            severity = Severity.OK

        report.metrics.append(
    MetricResult(
        name="behavioral_anomalies",
        value=float(score),
        severity=severity,
        details=(
            f"{len(anomalies)} anomalies detected "
            f"({criticals} critical, "
            f"{warnings} warning)"
        ),
        extra={
            "critical_count": criticals,
            "warning_count": warnings,
            "anomaly_count": len(anomalies),
        },
    )
)
        # Store full anomaly timeline
        report.anomalies = anomalies