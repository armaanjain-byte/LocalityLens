"""Golden benchmark smoke tests for metric calibration seeds."""

from __future__ import annotations

import json
from pathlib import Path

from localitylens.core.metrics import MetricNames
from localitylens.pipeline import run_pipeline


def test_benchmark_seed_metrics_stay_within_golden_expectations():
    root = Path("benchmarks")
    golden = json.loads((root / "golden_metrics.json").read_text(encoding="utf-8"))

    good = run_pipeline(root / "good_workflow.json")
    good_locality = good.by_name(MetricNames.LOCALITY_SCORE)[0]
    good_thrash = good.by_name(MetricNames.OSCILLATION_THRASHING)[0]
    assert good_locality.value >= golden["good_workflow.json"]["locality_score_min"]
    assert good_thrash.value <= golden["good_workflow.json"]["oscillation_thrashing_max"]

    thrashing = run_pipeline(root / "thrashing_workflow.json")
    thrashing_metric = thrashing.by_name(MetricNames.OSCILLATION_THRASHING)[0]
    assert thrashing_metric.value >= golden["thrashing_workflow.json"]["oscillation_thrashing_min"]
    assert (
        thrashing_metric.extra["thrashing_signal_count"]
        >= golden["thrashing_workflow.json"]["thrashing_signal_count_min"]
    )

    retrieval = run_pipeline(root / "retrieval_heavy_workflow.json")
    retrieval_metric = retrieval.by_name(MetricNames.OSCILLATION_THRASHING)[0]
    assert (
        retrieval_metric.extra["repeated_searches"]
        >= golden["retrieval_heavy_workflow.json"]["repeated_searches_min"]
    )
