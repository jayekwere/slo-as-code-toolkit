# Reliability calculations

Let target fraction be t, eligible events N, and good events G. Require integers 0 ≤ G ≤ N; boolean and fractional counts are rejected. Bad events B = N − G.

| Quantity | Formula |
| --- | --- |
| Observed availability or success percentage | 100 × G / N |
| Error-budget allowance in events | N × (1 − t) |
| Remaining allowance | N × (1 − t) − B |
| Budget consumption fraction | B / (N × (1 − t)) |
| Burn rate | (B / N) / (1 − t) |

Allowance uses Decimal arithmetic from the string form of the configured target, avoiding common binary floating-point artifacts such as 9.9999999999989 instead of 10. Intermediate allowance and consumption calculations are not rounded. JSON converts Decimal outputs to floats, so final representation has ordinary double precision. For operational displays round only at the presentation layer. Fractional allowed events are retained; an event cannot be fractionally successful. Negative remaining allowance means the budget is exceeded.

For 10,000 events, allowances are 10 at 99.9%, 5 at 99.95%, and 50 at 99.5%. Ten bad events against 99.9% consume exactly 100% of the observed budget and have burn rate 1. These are event budgets for the supplied observations, not estimates of unseen full-window traffic.

A burn alert fires only when both the long and short burn rates are strictly greater than the configured threshold, matching the generated Datadog `>` query. Equality is OK. At threshold r, the uniform-traffic budget fraction burned in L hours is approximately r × L / (days × 24). This approximation depends on traffic distribution.

For simulation, `--good` and `--total` describe the long window. Optional `--short-good` and `--short-total` describe the short window; by default both windows use the same explicitly synthetic ratio. The same aggregates are reused across the configured alert pairs. This is a scenario preview, not a time-series replay. `--incomplete` marks observations incomplete, resulting in NO_DATA.

With zero total events, availability, consumption, and burn rate are null, and alert state is NO_DATA. Missing observations also produce NO_DATA. No traffic is never treated as 100% reliability. Negative totals, good greater than total, nonfinite targets and invalid counters are errors.

The library's `window_counts` aggregates timezone-aware sample start timestamps in half-open [end − window, end) intervals. The left boundary is included and end is excluded. It requires a positive cadence dividing the window, aligned unique samples, and rejects future or timezone-naive samples. Coverage is complete only when every expected sample is present. Aggregate counts cannot establish continuous availability. Counter resets, stale scrapes, event delays and metric semantics must be handled in instrumentation before supplying counts.

Only metric-based SLOs are generated. Time-slice SLOs, monitor-based uptime SLOs, percentile averaging, retrospective Datadog history calculations, and automatic missing-data paging are outside version 0.1.0.
