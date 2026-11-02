# Official Release Please implementation plan

> **For agentic workers:** Use superpowers:executing-plans for implementation.

**Goal:** Protected main, official accumulated Release Please PR and tested GHCR
publication when the maintainer merges that proposal.

**Architecture:** Official action creates Releases, official manifest CLI maintains
PRs, Python computes only the repository-specific release-as policy, and explicit
dispatch builds/publishes the exact released tag after both native checks.

**Tech Stack:** Python/uv in Dev Container; official Release Please action v5.0.0
and CLI17.11.2 with Node24 only in CI; GitHub Actions, Git, gh, jq, Docker.

**Spec:** [Design](../specs/2026-11-02-automatic-versioning-design.md).

## Constraints and review focus

- No Node in product, installation, host or Dev Container; explicit CI exception only.
- No changes to compatibility baselines, no local publishing, no main bypass.
- Native checks, exact tag/source/version alignment, immutable image versions.
- Official updaters preserve old CHANGELOG and dependency pins.
- No recursive release, stale proposal dispatch or latest downgrade.

## Tasks

- [x] Protect main and enable Actions to create PRs with default read permissions.
- [x] Replace custom PR/version writer with official Release Please and manifest.
- [x] Preserve repository bump rules through read-only release-as helper.
- [x] Add native updater annotations/configuration and versioned CHANGELOG.
- [x] Publish only an existing released-tag dispatch, with read-only Git permissions.
- [x] Document both workflows, exact-tag recovery and Node exception.
- [x] Verify local tests/checks and independent review of final integration (33 directed cases).
- [ ] Update implementation PR, pass required checks and merge through protection.
- [ ] Verify the official automatic release proposal and its CI; leave merge to user.

## Execution record

The initial direct-main run41443352034 was cancelled before publication after the
user requested a PR workflow. The subsequent Python implementation was proposed in
PR1 but its runs41447021548/41446986894 were cancelled when the user explicitly
selected official Release Please. Main remained23faf2d and version0.1.0.

Pinned official source confirms action5.0.0 ignores release-as in manifest mode,
while CLI17.11.2 supports it; therefore both official interfaces are used. Native
TOML updater preserves formatting through tagged values, requiring `.name.value`
in the lock filter. The final directed suite passed33 cases, including legacy-tag
interference with latest and the official CLI override/freshness contract.

Publisher queue:max follows current GitHub documentation. Latest actionlint1.7.12
does not recognize that newer provider key: local lint suppresses only its exact
queue-key diagnostic, and hosted GitHub validation remains required. Latest reads
the Python manifest on protected main rather than ordering legacy upstream tags.
