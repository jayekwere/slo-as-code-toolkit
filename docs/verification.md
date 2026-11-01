# Verification evidence

The initial validation uses fictional definitions and a local Datadog contract simulator. No live Datadog credentials were provided, no live resources were created, and successful live integration is not claimed.

## Patch release 0.1.1

The final review and patch are described in [review-0.1.1.md](review-0.1.1.md). The patch adds 16 behavioral regression cases, for **104 passing tests** on local Python 3.14.6 and **95.25% statement coverage** (653 statements, 622 covered). [JUnit](../evidence/v0.1.1/junit.xml) and [coverage XML](../evidence/v0.1.1/coverage.xml) retain the measured results. [Hosted CI run 41310454797](https://github.com/jayekwere/slo-as-code-toolkit/actions/runs/41310454797) passed all five jobs on implementation commit [`d34f989ce0552be636d9b95f08bdab5e78581b61`](https://github.com/jayekwere/slo-as-code-toolkit/commit/d34f989ce0552be636d9b95f08bdab5e78581b61). Each Python matrix job passed all 104 tests. Exact hosted Python 3.12 coverage is retained in [hosted-ci.json](../evidence/v0.1.1/hosted-ci.json). The v0.1.1 GitHub release links the final evidence commit's passing CI and attaches its CI-built packages and checksums.

The independent static security review covered runtime modules, tests, examples, CI and supporting documentation. It reported no confirmed vulnerabilities under the documented threat model. Coverage was explicitly partial for generated evidence and dependency lock contents, which were selectively inspected. That result is not a formal security assurance or live API verification.

## Original 0.1.0 measured local results

- Python 3.14.6: 88 tests passed, 95.36% statement coverage (coverage gate: 85%).
- Ruff lint and formatting passed; strict Mypy passed for all 11 source modules.
- Locked runtime dependency audit: no known vulnerabilities; Gitleaks v8.30.1: no leaks found.
- The pinned Python 3.12 Docker image built successfully. Its complete demo passed as UID 10001 with networking disabled, a read-only root filesystem, and a bounded temporary filesystem.
- Wheel and sdist built twice with identical hashes. Exact release checksums are attached to the GitHub release.

## Hosted CI evidence

[CI run 41269015209](https://github.com/jayekwere/slo-as-code-toolkit/actions/runs/41269015209) passed on implementation commit [`382b5f3be9966d45e03fa18239c541bab0850e21`](https://github.com/jayekwere/slo-as-code-toolkit/commit/382b5f3be9966d45e03fa18239c541bab0850e21). All five jobs succeeded: Python 3.12, 3.13, Python 3.14, dependencies/secrets, and reproducible packages with an installed-wheel smoke test. Each matrix job ran all 88 tests. The run provides downloadable coverage, JUnit, demo, audit, secret-scan and distribution artifacts. Release notes identify the final documentation commit and its corresponding CI run.

## Reproduce

```sh
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy sloctl
uv run --frozen pytest --junitxml=junit.xml
uv run --frozen sloctl demo
uv run --frozen python scripts/reproducible_build.py
uv run --frozen pip-audit --disable-pip --require-hashes -r requirements.lock
bash scripts/scan_secrets.sh
```

Tests include mathematical boundaries, schemas and adversarial inputs, fictional API contract fixtures, actual loopback HTTP operations, idempotency, drift, ownership collisions, concurrent updates, stale plans, unknown write outcomes, authentication and authorization failures, rate limits, timeouts, partial failures, redaction, exports and CLI exit codes. Coverage is measured, with an 85% minimum enforced by pytest. See `evidence/junit.xml` and CI artifacts for exact test results for each commit.

The demo parses and validates all three service YAML files, computes budgets, generates three metric SLOs and six two-window burn monitors, saves before/desired plans, applies to the local simulator, verifies a second plan contains only noops, and simulates healthy and degraded windows. All six alerts fire for the fictional 10% failure scenario. Invalid examples are tested to fail before state creation.

The terminal SVG and PNG are recorded real CLI output. The HTML and Markdown files contain generated configuration and explicitly synthetic observations. The SQLite database is intentionally excluded from Git; recreate it with the demo. `tests/fixtures` contains constructed response examples rather than account captures.

The dependency audit found no known vulnerabilities in the locked runtime dependency set at validation time. The pinned Gitleaks scanner found no leaks. These results are point-in-time evidence, not guarantees against unknown vulnerabilities. CI repeats both checks and publishes their reports.

The build verifier produces wheel and source distribution twice under a fixed SOURCE_DATE_EPOCH and compares byte hashes. It also writes `dist/checksums.json`. CI smoke-tests the installed wheel outside the source tree, including the bundled examples. Wheel hashes can match across supported Python versions; source artifact hashes change when source or evidence changes. Each release attaches the checksums for its own exact commit.

The Python 3.12, 3.13 and 3.14 matrix, strict Mypy check, Ruff lint/format checks, dependency scan, secret scan, build reproducibility, and package smoke test run in GitHub Actions. Exact commit and CI links are recorded in release notes after completion.

## Known limits

- Live Datadog read-only verification remains pending until scoped credentials are available.
- Actual metric existence, counter semantics, production alert sensitivity, and provider-side monitor validation cannot be proved offline.
- Supported resources are metric-based SLOs and SLO burn monitors only, with one objective window per definition.
- No atomic remote compare-and-swap, multi-resource transaction, automatic deletion, or distributed lock exists.
- Removed service or alert identities are retained and are outside the supplied desired set; audit removals separately.
- Simulation reuses synthetic aggregate ratios rather than replaying production telemetry.
- The optional HTTP simulator is a loopback development service with no authentication.
