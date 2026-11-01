# Contributing

Use Python 3.12 or newer and install `uv==0.13.6`. Run:

```sh
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy sloctl
uv run --frozen pytest
uv run --frozen sloctl demo --output-dir /tmp/sloctl-contribution-demo
```

Tests bind one ephemeral loopback port and otherwise use local simulated HTTP transports. No real Datadog keys are needed. Do not skip coverage gates or replace live integration evidence with mock results. Add meaningful boundary/failure tests for changes to mathematics, ownership, retries, schemas, or mutation behavior. Keep fixtures fictional.

Submit focused pull requests describing the trigger, resulting behavior, and verification. Preserve read-only defaults, strict validation, explicit confirmation, no automatic deletion, and bounded requests. Never commit local databases, secret files, or real service measurements. Report vulnerabilities privately as described in SECURITY.md.

Dependency changes must update `uv.lock` and pass the audit. Action changes require reviewing upstream source and pinning a full commit SHA. Document API assumptions with official Datadog links. Do not add live mutation jobs to CI.
