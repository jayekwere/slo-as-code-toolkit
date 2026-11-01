# Security threat model

## Assets and trust boundaries

Assets are Datadog credentials, monitoring configuration, service definitions, approval fingerprints, local state, and audit records. Inputs cross boundaries from repository files into the parser, from a remote API into the planner, from an operator into an apply approval, and from structured data into terminal/HTML reports. Local files and the operator's operating-system account are trusted; a compromised host or stolen Datadog key is outside the toolkit's protection.

| Threat | Implemented control | Residual risk |
| --- | --- | --- |
| Executable YAML or alias expansion | Safe loader; no aliases; duplicate-key rejection; 64 KiB bound; recursion errors fail validation | Local special files can block reads; use regular trusted files |
| Misleading SLO math | Strict finite targets; integer counts; Decimal allowance; missing/zero data explicit; boundary tests | Instrumentation must prove good is a subset of total |
| Accidental live mutation | Offline default; read-only client; explicit apply; confirmation; second live authorization flag | Authorized operator can approve a wrong definition |
| SSRF or key exfiltration | Fixed HTTPS regional allowlist; no redirects or ambient proxy configuration | Host CA trust and endpoint compromise remain external |
| Credential leakage | Environment-only keys; no request-header/body logging; sanitized API errors; report redaction of active keys | Secrets unknown to the process cannot be automatically recognized everywhere |
| Taking over unmanaged monitors | Two ownership tags and duplicate detection | A privileged external actor can forge ownership tags |
| Duplicate creates after timeout | Never retry POST/PUT; discover stable identity on next plan | Concurrent remote writers can create duplicates; duplicates block further work |
| Concurrent configuration overwrite | Local exclusive lock; approval fingerprint; per-write read; verification | Datadog lacks CAS; require external serialization |
| Partial API failure | Stop sequential apply; retain successful state; audit and re-plan recovery | No multi-resource transaction or automatic rollback |
| Unbounded remote responses | Streamed 4 MB body cap; four read attempts; timeouts; 100-page cap | Per-phase timeouts are not a whole-process deadline |
| Report script injection | HTML escaping and no executable data templates | Reports disclose ordinary configuration; protect as needed |
| Dependency or CI compromise | Committed dependency lock; pinned action SHAs; dependency audit; secret scan; minimal workflow permission | Updating pinned sources requires review |
| Local simulator misuse | Loopback-only optional server, Host/Origin and JSON content-type checks, request bounds, SQLite transactions | Unauthenticated local clients can mutate a sandbox; no production deployment |

No arbitrary code evaluation, plugin execution, shell interpolation, remote deletion, paid provisioning, or automatic live credential detection exists. Secret scanning and tests reduce risk but are not a claim of formal security assurance.

## Verification

Tests cover malicious tags, YAML aliases, duplicate fields, deeply nested inputs, invalid bytes, impossible windows, response schemas, redirects, oversized bodies, bad IDs, authentication failures, timeouts, bounded retries, concurrent changes, stale plans, and partial recovery. See `docs/verification.md` for measured results. No external security audit or live Datadog validation is claimed.
