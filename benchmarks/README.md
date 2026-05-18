# LocalityLens Benchmark Seeds

These traces are intentionally small golden fixtures, not a calibrated corpus yet.
They exist to keep metric behavior stable while larger empirical calibration is built.

- `good_workflow.json`: mostly focused file movement.
- `thrashing_workflow.json`: intentional A/B oscillation.
- `retrieval_heavy_workflow.json`: repeated equivalent searches.
- `golden_metrics.json`: coarse expectations for regression tests.
