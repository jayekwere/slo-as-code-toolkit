# Final review and patch 0.1.1

Reviewed baseline: `064174800e16a2d3c5675831d88ab826c4b7f814` (v0.1.0). Review date: November 1, 2026. Scope: runtime, CLI, mathematics, API contracts, ownership/reconciliation, reports, local server, tests, examples, CI and release tooling. An independent static baseline auditor reviewed the code without network access or application execution. Generated evidence and dependency locks were selectively inspected. No confirmed attacker privilege escalation or production vulnerability was established under the documented threat model. The following correctness and defense-in-depth issues were fixed and reproduced with regression tests.

| Trigger in 0.1.0 | Patch behavior | Evidence |
| --- | --- | --- |
| Apply new `api`, `api-worker`, and `api-worker-jobs` definitions together | Replace complete quoted SLO references, so each monitor points at its own created SLO | End-to-end prefix-service regression |
| Monitor status or timestamps change after planning | Approval fingerprint and pre-write checks use ID plus managed fields; actual query/tag/ID changes still invalidate approval | Volatile-status and managed-drift regressions |
| A remote resource carries multiple `sloctl-id` tags | Fail closed before writing ambiguous ownership | Multiple-identity regression |
| Audit parent directory is unavailable | Open the audit before any mutation; flush each returned successful write | Zero-mutation audit-failure regression |
| API returns a different ID after an update | Stop with a sanitized identity-mismatch error | Response identity regression |
| Active environment credential appears in a report's summary fields | Redact once before rendering both summary and details in every format | HTML/Markdown/JSON redaction regressions |
| Browser sends a cross-origin or text/plain write to the local simulator | Reject any Origin, unexpected Host, or non-JSON POST/PUT | Actual loopback rejection tests, with no state change |
| Malformed/deep API or simulator payload | Return bounded, sanitized failures instead of unhandled parser/serialization errors | Malformed payload regressions |
| Unsupported route/method or invalid pagination | Reject explicitly; use SQL LIMIT/OFFSET instead of loading all records | Simulator route/pagination regressions |
| Demo output already exists | Return documented input exit code 2 | CLI regression |

The locked dependency audit found no known runtime vulnerabilities, and the pinned Gitleaks scanner found no leaks. Repeated wheel/source builds were byte-identical. The unprivileged container demo passed with networking disabled and a read-only root filesystem. These are point-in-time verification results.

The local suite passes 104 tests with 95.25% statement coverage. Strict Mypy and Ruff checks pass. CI repeats the full suite on Python 3.12, 3.13 and 3.14, checks the dependency lock and known vulnerabilities, scans Git history for secrets, builds each distribution twice and compares hashes, and smoke-tests the installed wheel outside the checkout. Release notes identify the exact passing commit and CI run. The original v0.1.0 evidence is retained separately.

Approval hashes intentionally change format in 0.1.1. Generate a fresh plan after upgrading instead of reusing an old `--expected` fingerprint. The printed plan still contains the complete response for inspection, but server-generated status metadata does not bind approval. Configuration fields managed by the toolkit and resource IDs do bind it. Datadog still has no atomic compare-and-swap; serialize live writers externally. Local audit I/O failures after a successful write remain possible, so inspect remote state and re-plan after an error.

The optional HTTP simulator now accepts JSON mutations only from clients using the actual loopback Host and no Origin header. It remains unauthenticated and development-only; do not forward the port. No live Datadog resources or paid infrastructure were created. Live read-only validation remains pending scoped credentials.
