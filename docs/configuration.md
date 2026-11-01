# Configuration reference

A definition is one UTF-8 YAML or JSON object, at most 64 KiB. Schema version 1 is required. Unknown fields, duplicate mapping keys, YAML aliases, executable tags, coercions, nonfinite numbers, and unsupported metric expressions are rejected. Files are trusted local paths; do not point the tool at devices or untrusted FIFOs.

```yaml
version: 1
name: public-api
kind: availability
target: 99.9
days: 30
good_query: "sum:public_api.good{env:demo}.as_count()"
total_query: "sum:public_api.total{env:demo}.as_count()"
alerts:
  - name: fast
    long_hours: 1
    short_minutes: 5
    burn_rate: 14.4
  - name: slow
    long_hours: 6
    short_minutes: 30
    burn_rate: 6.0
```

| Field | Contract |
| --- | --- |
| `version` | Integer 1 |
| `name` | Lowercase service identity, starts with a letter, up to 63 letters/digits/hyphens |
| `kind` | `availability`, `success`, or `latency` |
| `target` | Finite numeric percentage strictly between 0 and 100 |
| `days` | Integer 7, 30, or 90 |
| `good_query`, `total_query` | Distinct summed count queries, at most 2048 characters each |
| `latency_threshold_ms` | Positive number, required for latency; metadata for instrumented good counter |
| `alerts` | At most ten alerts; omitted defaults to fast and slow above; empty disables desired alerts |
| Alert `name` | Unique lowercase identity, up to 41 characters |
| `long_hours` | Integer from 1 through 48 |
| `short_minutes` | Positive integer strictly smaller than long_hours × 60 |
| `burn_rate` | Positive finite number no greater than reciprocal error-budget fraction |

Supported query grammar is `sum:METRIC{SCOPE}.as_count()`, with metric letters, digits, underscore and dots; scopes allow letters, digits, underscore, colon, wildcard, dot, comma, slash, equals and hyphen. Expressions, distribution percentile queries, grouping, formulas, and secret substitution are intentionally unsupported. The backend must supply good events as a subset of total events with matching scope and count units. The parser cannot prove that semantic property from metric names.

Targets with low reliability may require custom lower burn thresholds instead of the defaults. Thresholds are not automatically scaled when the objective window changes. Choose them based on the budget fraction and response time you intend.

A latency definition must declare a threshold, for example `latency_threshold_ms: 250.0`, and reference a good-event counter incremented only for valid requests completing within that threshold. The total counter includes all eligible requests, including slow or failed requests. The threshold is not sent as an unsupported Datadog field.

Examples are fictional: public API 99.9% availability, authentication API 99.95% request success, background processing 99.5% successful job completions. Availability here is an event ratio, not a claim about continuous uptime. Deliberately invalid files live in `examples/invalid/`. JSON and YAML are equivalent input formats. The JSON authentication example duplicates the YAML identity, so use either version in a single invocation.

Definitions and tags form the versioned desired state. Commit changes and review `plan` output. Schema changes require explicit version migration; unknown future versions fail validation.
