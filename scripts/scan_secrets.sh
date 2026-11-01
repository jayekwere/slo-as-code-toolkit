#!/usr/bin/env bash
set -euo pipefail
# Official release v8.30.1, SHA-256 from the upstream checksum manifest.
scanner_dir=$(mktemp -d)
trap 'rm -rf "$scanner_dir"' EXIT
curl --fail --location --retry 2 --max-time 60 \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
  --output "$scanner_dir/scanner.tar.gz"
printf '%s  %s\n' '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb' "$scanner_dir/scanner.tar.gz" | sha256sum --check --strict
tar -xzf "$scanner_dir/scanner.tar.gz" -C "$scanner_dir" gitleaks
"$scanner_dir/gitleaks" git --redact --no-banner --report-format json --report-path gitleaks-report.json
