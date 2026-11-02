# Automatic versioning implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically publish a tested semantic version on each main push.

**Architecture:** Prepare a deterministic release commit and transfer it as a Git
bundle. Test that exact tree on both native runners; publish its images, Git tag,
source version commit and GitHub Release only after those checks pass.

**Tech Stack:** Python standard library, uv, Git, GitHub Actions, Docker Buildx.

**Spec:** [Design](../specs/2026-11-02-automatic-versioning-design.md).

## Global constraints

- Python/tests/builds run in the Linux Dev Container.
- major for breaking changes, minor for feat/fix, patch for other commits.
- No changes to compatibility baselines, Node runtime or local publishing tools.
- No forced branch/tag updates; main and Git tag are pushed atomically.

## Review focus

- Multiple commits and breaking footers choose the highest increment.
- Old upstream tags do not select the Python version.
- Reruns produce the same release commit and do not bump twice.
- Concurrent main changes and conflicting tags prevent promotion.
- Both native runners use the prepared tree; a failed gate cannot publish.

### Task 1: Release preparation

**Files:** `.release.json`, `scripts/ci_version.py`, `tests/unit/test_ci_version.py`.

**Interfaces:** `next_version(current, messages)`; CLI `prepare --output PATH`
creates `release.bundle`, `release.json`, `notes.md`. Metadata carries source,
revision, version and tag. Default operation never pushes.

- [x] Write and observe failing semantic-version and real-Git preparation tests.
- [x] Implement parsing, stamping, deterministic commit/bundle, notes and anchor.
- [x] Verify version/lock/labels/docs agreement, bundle restoration and rerun SHA.

### Task 2: CI integration

**Files:** `.github/workflows/ci.yaml`, `tests/unit/test_ci_workflow.py`.

**Interfaces:** prepare job outputs version/revision; both checks and publish
restore `release.bundle`. Publish consumes exact tested image IDs.

- [x] Add failing gate, version promotion and real-Git publication tests.
- [x] Add prepare/restore, atomic Git publication, version Docker tag and Release.
- [x] Verify success and refusal paths without remote writes in tests.

### Task 3: Delivery

**Files:** `docs/ci.md`, README guides and development guide.

- [x] Document increments, source sync, tags, recovery and token behavior.
- [ ] Run Ruff, mypy, full pytest/coverage, compatibility, docs check, uv build,
  actionlint and real disposable Mealie E2E in the Dev Container.
- [ ] Review, commit, push; verify actual native CI, Git version/tag, Release,
  public GHCR versions/digests and anonymous runtime startup.

## Execution record

Ruling: continue in the existing clean workspace with a task branch. The shared
Dev Container is already bound here and remote delivery on main is authorized.
The pre-existing published Python source d9cccee is the bootstrap anchor.

Local directed checks: 23 passed. These execute the actual publisher Bash against
real bare Git repositories and a Docker boundary fake, including a main update
between preflight and atomic push. A clean shallow clone restores the bundle;
repeated preparation produces the identical commit. Ruff and actionlint passed.
Independent review: no blocking bugs found; remaining proof is the hosted run
and actual GitHub/GHCR publication, which local tests cannot establish.
