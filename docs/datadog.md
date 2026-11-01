# Datadog integration

The client implements documented v1 metric SLO and monitor operations. No paid Datadog account is required for the offline workflow. Offline tests and constructed contract fixtures do not prove live integration.

| Operation | Endpoint |
| --- | --- |
| List SLOs | GET `/api/v1/slo?limit=1000&offset=N` |
| Create/update SLO | POST `/api/v1/slo`, PUT `/api/v1/slo/{id}` |
| List monitors | GET `/api/v1/monitor?page_size=1000&page=N` |
| Create/update monitor | POST `/api/v1/monitor`, PUT `/api/v1/monitor/{id}` |

No DELETE operations exist. SLO responses use a `data` array; monitor listing is a direct array and monitor write responses are single objects. Resource IDs, query shape, and metric thresholds are validated. Server-managed extra fields are accepted; comparison is limited to desired fields. Monitor options outside the desired subset do not independently cause drift. SLO thresholds and tags are authoritative for an explicitly owned resource.

Generated monitor queries use the documented form:

```text
burn_rate("SLO_ID").over("30d").long_window("1h").short_window("5m") > 14.4
```

The monitor type is `slo alert`, with the same critical threshold in `options.thresholds`. Monitor references are resolved after SLO creation. Plans use `REF:service-name` placeholders for new SLOs; these are replaced before an API write.

## Regions and credentials

`--site` accepts only `datadoghq.com`, `us3.datadoghq.com`, `us5.datadoghq.com`, `datadoghq.eu`, `ap1.datadoghq.com`, `ap2.datadoghq.com`, `uk1.datadoghq.com`, `ddog-gov.com`, or `us2.ddog-gov.com`. Each maps to HTTPS `api.SITE`. Arbitrary endpoints, redirects, ambient proxy settings, and localhost live endpoints are rejected or disabled. The optional simulator server always binds loopback and never forwards requests.

Use environment variables `DD_API_KEY` and `DD_APP_KEY` from an approved secret store. Do not put keys in definitions, command arguments, shell history, source, CI output, or report files. Read-only keys should have `slos_read` and `monitors_read` only. A separately authorized mutation identity additionally needs `slos_write` and `monitors_write`, subject to the account's resource restrictions. There is no need for administrative credentials or SLO correction permissions.

HTTP connect timeout is 3 seconds, other request phases are 10 seconds. Responses are bounded to 4 MB and pagination to 100 pages. GET retries are capped at four total attempts, with delays capped at 5 seconds. HTTP 429 and 5xx, plus transport failures, are retried on reads. Authentication/authorization failures fail immediately. POST and PUT are never automatically retried: an unknown write outcome must be inspected and re-planned. This prevents duplicate creates after ambiguous timeouts. Pagination failure aborts the plan before mutation.

## Latest availability check

On November 1, 2026, v0.1.2 credential checks found no usable credentials in the named sources. `plan --live` stopped locally with exit 4 before any HTTP send. Live integration remains unverified, and no Datadog resources were changed. See the [recorded evidence](../evidence/live-read-only/2026-11-01.json) and [verification notes](verification.md) for exact scope and limitations.

## Optional live read-only verification

After separately configuring scoped credentials in your environment:

```sh
sloctl plan examples/public-api.yaml --live --site datadoghq.com --output live-plan.json
sloctl drift examples/public-api.yaml --live --site datadoghq.com
```

These issue only GET calls. A missing desired resource yields create proposals and drift exit 3; it does not create it. Review the real account identity and scopes independently. No live verification was performed for the initial release because no Datadog credentials were provided. Metric query semantics and monitor validation must be checked in the intended account before an authorized live apply.

A live mutation requires an explicit operator decision, `apply --live --allow-live-mutations`, and interactive confirmation or `--yes`. Do not run it just to validate this project. Use `--expected` with the reviewed fingerprint to prevent applying a changed plan. Live atomicity is limited by the API; see the operations guide.

## Source references

- [Create an SLO](https://docs.datadoghq.com/api/latest/service-level-objectives/create-an-slo-object/)
- [Update an SLO](https://docs.datadoghq.com/api/latest/service-level-objectives/update-an-slo/)
- [List SLOs](https://docs.datadoghq.com/api/latest/service-level-objectives/get-all-slos/)
- [Create a monitor](https://docs.datadoghq.com/api/latest/monitors/create-a-monitor/)
- [Burn-rate alert mathematics and supported windows](https://docs.datadoghq.com/service_level_objectives/burn_rate/)
- [Permissions](https://docs.datadoghq.com/account_management/rbac/permissions/)

These references informed the implementation. The local fixtures are fictional contract examples, not captured account responses.
