# Operations and recovery

## Review and apply

1. Commit definitions and validate all files together.
2. Run `sloctl plan FILE... --output plan.json` against the intended backend.
3. Review every create/update, identity tag, metric query, target and window. Protect the plan as operational configuration.
4. Copy `fingerprint` from the plan. Run `sloctl apply FILE... --expected HASH`; confirm the displayed actions. Use the same state/site/live settings as the reviewed plan. Unattended approved jobs may pass `--yes`.
5. Require successful verification and `sloctl drift FILE...` exit 0. Retain audit records and commit history.

The audit is append-only JSON Lines containing action, resource kind, stable key, and remote ID. It omits credentials and API response bodies. Each successfully returned write is recorded immediately. An audit-write failure stops further work but cannot roll back a remote write. A transport error may mean a write succeeded without an audit entry. Inspect remote state and re-plan.

Stable ownership requires both `managed-by:sloctl` and `sloctl-id:NAME` (monitors append `:ALERT`). A matching identity without ownership, or duplicate matching identities, blocks apply. Resources with no matching identity are left alone. Never manually copy identity tags onto unrelated resources.

A fresh read is performed after approval and before each write. A local exclusive lock prevents overlapping apply processes sharing the same state path. This is not a distributed lock and the APIs do not expose atomic conditional updates. Serialize live writers with an external deployment lock; prohibit interactive edits during a live apply. A change between the final read and write can still race. Post-apply verification reports remaining drift.

## Partial failure

Multi-resource changes are sequential: SLO first, then its monitors. A failure stops immediately. Already successful changes remain. Do not blindly retry a saved HTTP write or delete resources to restart. Inspect the audit and account, run a fresh plan, verify ownership, and approve only the remaining changes. The next run discovers previously created resources by tags, including a create whose response was lost. If duplicates exist, stop and resolve them manually after identifying the authoritative resource.

If authentication fails, use the correct scoped credentials; never escalate to an admin key as a workaround. Rate-limit and transient reads retry within bounds. After exhausted retries, wait outside the tool and start a new read-only plan. Mutation errors require inspection regardless of status.

A process killed during apply can leave `STATE.lock`. Confirm no writer remains before manually removing that exact file. Preserve the audit first. SQLite transactions protect each simulator write; they do not make an entire apply atomic.

There is no prune, destroy, or automated rollback command. Removing a definition or alert does not delete its remote resource and does not enumerate it as desired drift. Review removed resources separately. Reverting a Git commit and reviewing/applying a fresh plan is the supported configuration rollback; deleted or unrelated resources are never automatically reconstructed.

## Local server and state

The default simulator uses HTTPX MockTransport and a persistent SQLite database. It exercises real request and response serialization without network access. An optional facade exposes the same supported routes:

```sh
sloctl serve --state sandbox.db --port 8765
# In another terminal:
curl http://127.0.0.1:8765/api/v1/slo
```

The facade is for local contract development, not production hosting. It has no authentication and trusts local users. Do not forward its port. It accepts bounded JSON requests and rejects unsupported routes. The CLI normally uses its in-process transport; point `--state sandbox.db` at the same file to inspect the standalone server state. Do not run direct server writes concurrently with apply.

Reports use exclusive file creation to avoid accidental overwrite. The demo also requires a new output directory. SQLite, audit, and lock files are local operational artifacts and are ignored by Git. To reset a fictional sandbox, stop its server and deliberately remove its database after retaining evidence.

## Container

Build with `docker build -t sloctl .`. Run with `docker run --rm sloctl demo --output-dir /tmp/demo`. The image runs as an unprivileged user and does not include credentials. Use a writable mounted workspace for persistent local state and reports. Docker is optional; the native workflow is the reference verification path.
