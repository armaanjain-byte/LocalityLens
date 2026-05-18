# LocalityLens Audit Report

**Trace ID:** `my_trace_ffbd21d6`  
**Global Verdict:** `CRITICAL`

## Summary Analysis Metrics

| Status | Metric Name | Core Value | Diagnostic Analysis Details |
| :--- | :--- | :---: | :--- |
| `OK` | **behavioral_anomalies** | `0.0000` | 0 anomalies detected (0 critical, 0 high) |
| `LOW` | **churn_ratio** | `0.2500` | 1 writes / 4 file events (reads + writes). |
| `CRITICAL` | **context_entropy** | `1.0000` | Relative transition entropy: 1.0000 (2 unique transition pairs, 2 total). Higher values indicate fragmented workflows. |
| `CRITICAL` | **dependency_jump_radius** | `3.0000` | Average dependency jump radius: 3.0000 hops (4/4 disconnected transitions). |
| `OK` | **locality_score** | `0.7500` | 3/4 transitions stayed within a 10-event semantic context window. |
| `OK` | **oscillation_thrashing** | `0.0000` | 0 oscillation loops detected (rate: 0.00%). Top pairs: None |
| `CRITICAL` | **semantic_continuity** | `0.0000` | 0/4 transitions remained inside semantic dependency neighborhoods. |
| `OK` | **transition_concentration** | `0.5000` | Dominant transition ratio: 0.5000. Top transitions: src/main.py->src/utils.py(1), src/utils.py->src/main.py(1) |
| `OK` | **waste_gap_count** | `0.0000` | 0 idle gap(s) >=30.0s detected; total idle time: 0.0s. |