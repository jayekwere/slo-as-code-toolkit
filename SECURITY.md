# Security policy

Version 0.1.x receives best-effort security fixes. Use only the latest patch release and review the [threat model](docs/threat-model.md) before live operation.

Report vulnerabilities through the repository's private vulnerability reporting feature if enabled, or contact the repository owner privately through GitHub. Do not post real credentials, account identifiers, or exploitation details in a public issue. Include the affected version, minimal fictional reproducer, expected behavior, and impact. There is no guaranteed response SLA.

Keep keys in environment variables or an approved secret store. Rotate any exposed key immediately. This repository does not require secrets to run its tests or demo. Offline testing is not proof of live integration. The optional local simulator is unauthenticated and must remain on loopback.
