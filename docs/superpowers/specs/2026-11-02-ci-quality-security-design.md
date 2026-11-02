# CI quality, dependency review and release evidence

The user approved applying the seven CI recommendations and evaluating the overlapping
second list. Implementation stays in Python and Linux Dev Containers; only the existing
Release Please workflow installs Node. Actions themselves may use their bundled runtimes.

## Scope and decisions

- Run runtime CI on main pushes, pull requests and manual dispatch, eliminating branch
  push duplication. Preserve both native architectures and the release dispatch contract.
- Check workflows permanently with pinned actionlint and zizmor tools. Keep any actionlint
  exception limited to the unsupported `publish.concurrency.queue` property.
- Add CodeQL for Python/Actions and dependency review for newly introduced HIGH/CRITICAL
  vulnerabilities. Validate PR titles against the configured Release Please commit types.
  Supplement graph-based review with a direct uv.lock advisory diff, using the temporary
  read-only GitHub token only against the official endpoint; do not use personal secrets.
- Keep Renovate as the sole version-update bot: weekly grouped updates, uv lock maintenance,
  Actions/Docker pins, and custom extraction of the Trivy and Release Please CLI pins.
  A second Dependabot version-update configuration would duplicate its ownership.
- Reuse the image scanner weekly against immutable published amd64/arm64 digests. Preserve
  evidence and distinguish new actionable findings from unchanged known findings.
- Preserve the existing independent coverage gates (90% lines, 85% branches). Add a visible
  verification summary rather than weakening or duplicating those gates.
- Bind SBOM and signed workflow provenance to the exact tested image digests, verify the
  attestations, and retain release evidence as GitHub Release assets. Do not rebuild images
  during publication or modify the public MCP contract and immutable fixtures.

## Alternatives evaluated

Use Renovate rather than running competing Renovate and Dependabot version updates.
Use GitHub attestations for existing image digests rather than changing the docker-save
promotion format to carry BuildKit attestations. Keep the current runtime Trivy gate;
there is no BEDCA image or variant in this repository to add to its matrix.

## Verification and delivery

Behavioral script tests run in the existing Dev Container, followed by the repository
checks in docs/development.md, native local container tests, workflow lint, configuration
validation, build and compatibility evidence. Remote CodeQL, dependency-review, scheduling,
OIDC signing and Release asset upload require the workflows to be pushed and run on GitHub;
local checks must not be described as remote proof. This task prepares local reviewable
changes and does not publish commits, images or releases.
