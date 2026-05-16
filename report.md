# LocalityLens Audit Report

**Trace ID:** `my_trace`  
**Global Verdict:** `CRITICAL`

## Summary Analysis Metrics

| Status | Metric Name | Core Value | Diagnostic Analysis Details |
| :--- | :--- | :---: | :--- |
| 🔵 `LOW` | **churn_ratio** | `0.2500` | 1 writes / 4 file events (reads + writes). |
| 🔵 `LOW` | **locality_score** | `0.6667` | 2/3 transitions stayed within a 10-event context window. |
| 🟣 `CRITICAL` | **thrash_file_count** | `1.0000` | 1/2 files revisited ≥3x. Top: src/main.py(3) |
| 🟢 `OK` | **waste_gap_count** | `0.0000` | 0 idle gap(s) ≥30.0s detected; total idle time: 0.0s. |