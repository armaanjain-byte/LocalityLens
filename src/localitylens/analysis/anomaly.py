"""Behavioral anomaly detection for agent traces."""

from __future__ import annotations

from collections import Counter, deque
from pathlib import PurePosixPath

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class AnomalyAnalyzer:
    """
    Detect behavioral instability patterns in agent traces.

    Detects three anomaly classes:
    - hotspot_revisit: a single target accessed >= 15, 30, or 60 times
    - oscillation:    A → B → A → B alternation pattern
    - semantic_jump:  transition between different top-level directory roots
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del smap

        anomalies: list[dict] = []
        recent: deque[str] = deque(maxlen=25)
        revisit_counter: Counter[str] = Counter()
        previous: str | None = None
        oscillation_count = 0

        for idx, event in enumerate(trace.events):
            target = getattr(event, "target", None)
            if not target:
                continue

            # ------------------------------------------------------------------
            # Revisit pressure
            # ------------------------------------------------------------------
            revisit_counter[target] += 1

            if revisit_counter[target] in (15, 30, 60):
                anomalies.append({
                    "step": idx,
                    "severity": "CRITICAL",
                    "type": "hotspot_revisit",
                    "message": f"{target} revisited {revisit_counter[target]} times",
                })

            # ------------------------------------------------------------------
            # Oscillation loops  A → B → A → B
            # ------------------------------------------------------------------
            recent.append(target)

            if len(recent) >= 4:
                a, b, c, d = list(recent)[-4:]
                if a == c and b == d and a != b:
                    oscillation_count += 1
                    anomalies.append({
                        "step": idx,
                        "severity": "HIGH",          # was "WARNING" — not a valid Severity
                        "type": "oscillation",
                        "message": f"Oscillation between {a} <-> {b}",
                    })

            # ------------------------------------------------------------------
            # Semantic jump bursts (different top-level directory)
            # ------------------------------------------------------------------
            if previous and previous != target:
                prev_dir = str(PurePosixPath(previous).parent)
                curr_dir = str(PurePosixPath(target).parent)
                if prev_dir != curr_dir and prev_dir != "." and curr_dir != ".":
                    anomalies.append({
                        "step": idx,
                        "severity": "LOW",
                        "type": "semantic_jump",
                        "message": f"{previous} -> {target}",
                    })

            previous = target

        # ----------------------------------------------------------------------
        # Aggregate score
        # ----------------------------------------------------------------------
        criticals = sum(1 for a in anomalies if a["severity"] == "CRITICAL")
        highs = sum(1 for a in anomalies if a["severity"] == "HIGH")

        score = criticals * 3 + highs
        score_rate = score / max(1, len(trace.events))

        if score_rate > 0.25:
            severity = Severity.CRITICAL
        elif score_rate > 0.10:
            severity = Severity.HIGH      # was Severity.WARNING — does not exist
        elif score_rate > 0:
            severity = Severity.MEDIUM
        else:
            severity = Severity.OK

        report.metrics.append(
            MetricResult(
                name=MetricNames.BEHAVIORAL_ANOMALIES,
                value=float(score),
                severity=severity,
                details=(
                    f"{len(anomalies)} anomalies detected "
                    f"({criticals} critical, {highs} high)"
                ),
                extra={
                    "critical_count": criticals,
                    "high_count": highs,
                    "anomaly_count": len(anomalies),
                    "raw_score": score,
                    "score_rate": round(score_rate, 4),
                },
            )
        )

        # Persist full anomaly timeline onto the report (declared field in AnalysisReport)
        report.anomalies = anomalies
