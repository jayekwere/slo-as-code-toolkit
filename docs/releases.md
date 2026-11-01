# Releases and versioning

Package versions follow semantic versioning. Version 0.x may evolve, but schema version 1 changes must remain explicit; unsupported schema versions fail validation. Release notes must distinguish offline contract evidence from any optional live read-only verification.

1. Update `project.version`, release notes, and documentation.
2. Run `uv lock`, then commit the resulting lock alongside source changes.
3. Require all CI jobs on that exact commit to pass, including the Python matrix, lint, types, dependency audit, secret scan and reproducible builds.
4. Build two wheel/sdist pairs with the same `SOURCE_DATE_EPOCH`; compare SHA-256 hashes. CI performs this check and uploads the distributions.
5. Create an annotated version tag only after validation, then publish a GitHub release with tested commit, CI URL, counts, coverage, checksums, artifacts, and limitations. Never include Datadog credentials.
6. PyPI publication is a separate decision; use a trusted publishing identity if configured. This project does not configure automatic PyPI uploads.

For recovery, revert a bad source change and release a new patch. Never replace an existing published tag or artifact silently.
