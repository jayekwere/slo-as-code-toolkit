# Changelog

## 0.1.1

- Resolve newly created SLO references exactly, including service names sharing a prefix.
- Bind approvals and pre-write checks to resource identity and managed configuration instead of volatile monitor status metadata.
- Reject ambiguous multiple ownership identity tags and mismatched update-response IDs.
- Open audit output before starting writes and flush each successful action.
- Redact active credential values in HTML summary cells as well as report details.
- Reject browser-origin requests, unexpected Host headers, and non-JSON mutations on the optional loopback simulator.
- Enforce simulator routes/methods and bounded SQL pagination; return explicit failures for malformed nested payloads.
- Handle deep API JSON/serialization and invalid encodings as sanitized API errors. Read response chunks in bounded pieces.
- Return input exit code 2 for an existing/unwritable demo destination.
- Add targeted regression coverage and updated offline verification evidence. No live Datadog verification is claimed.

## 0.1.0

Initial metric SLO toolkit with strict YAML/JSON definitions, event budgets, burn-alert generation, local API simulation, explicit reconciliation, audit and recovery, reports, tests and CI. Live Datadog verification is not included in the release evidence.
