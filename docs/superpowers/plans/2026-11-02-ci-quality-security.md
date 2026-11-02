# CI Quality and Security Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for integration, with independent
> parallel work for the dependency and scheduled-security domains and one final review.

**Goal:** Apply the approved CI safeguards, remove duplicate executions and retain
verifiable evidence for exact tested release images.

**Architecture:** Retain the Dev Container verification matrix. Add focused workflows and
Python helpers for policy and scanning; attach attestations to existing digests and keep
release evidence separate from ephemeral CI artifacts.

**Tech Stack:** Python 3.14, uv, Docker, GitHub Actions, CodeQL, Trivy, actionlint, zizmor.

**Spec:** docs/superpowers/specs/2026-11-02-ci-quality-security-design.md

## Global constraints

- Python, tests and builds run only in the Linux Dev Container.
- Preserve the public MCP contract, fixtures, both native architectures and exact images.
- No additional Node installation outside the existing Release Please workflow.
- No remote writes or publication during implementation and local verification.
- Preserve coverage gates at 90% lines and 85% branches.

## Review focus

- Untrusted PR titles and fork changes must never gain personal secrets or write permissions.
- Failed/partial scans must never be mistaken for an unchanged clean published image.
- Re-running old releases must not reduce latest or overwrite version digests.
- SBOM subjects must match their architecture-specific manifests, not the other image.
- Artifact expiry or unavailable dependency data must be visible, not silently bypassed.

### Task 1: Dependency and PR policies

Files: focused CodeQL/dependency-review/PR policy workflows, scripts/check_pr_title.py,
tests/unit/test_pr_title.py, renovate.json and any scoped Renovate extraction tests.

- [x] Add behavioral tests for valid configured types, invalid/empty/multiline titles,
  breaking/scoped titles and untrusted text; run them RED in the Dev Container.
- [x] Implement title validation from release-please-config.json and wire edited/synchronize
  PR events safely through the event file, with read permissions and no interpolation.
- [x] Add pinned CodeQL and dependency review actions. Keep runtime checks and personal secrets out
  of fork-PR analysis; fail on new HIGH/CRITICAL vulnerabilities.
- [x] Configure weekly Renovate grouping, lock maintenance and custom CLI/scanner updates;
  validate extraction and configuration without adding npm files to the product.
- [x] Run the focused tests and record evidence.

### Task 2: Published image security surveillance

Files: focused scheduled workflow, scripts/published_security.py, scanner extensions only
if needed, and tests/unit/test_published_security.py.

- [x] Test digest/architecture selection, new versus unchanged findings, incomplete scans,
  and missing/expired baseline behavior RED, then implement the minimal helper.
- [x] Resolve immutable published digests; reuse scan_runtime.py in the Dev Container.
  Scan both architectures without rebuilding or promoting images.
- [x] Persist validated comparison evidence, fail visibly for operational failures and new
  actionable findings, and avoid repeated notifications for unchanged findings.
- [x] Run focused behavioral tests and record limitations of local-only verification.

### Task 3: Workflow validation and release evidence

Files: ci.yaml, focused workflow quality workflow, Python lint/summary helpers, scoped
actionlint/zizmor configuration, and targeted behavioral/workflow tests.

- [x] Preserve the publisher's existing behavioral tests; add failure cases for any new
  publication boundary before changing implementation.
- [x] Limit runtime push trigger to main and add pinned disposable workflow lint tools.
- [x] Add coverage/test/security summaries while retaining existing coverage gates.
- [x] Attest tested digests with matching SBOMs; verify before release promotion and retain
  release reports/SBOMs/checksums as release assets. Preserve publication idempotence.
- [x] Validate workflow syntax and security with narrowly justified exceptions only.

### Task 4: Integration and verification

Files: docs/ci.md, docs/development.md, generated docs if required and this execution record.

- [x] Update documentation with events, checks, findings policy, bot ownership, permissions,
  recovery and verification commands; regenerate docs and check compatibility.
- [x] Run Ruff, format, mypy, full pytest with coverage/JUnit, compatibility checks, uv build,
  workflow linters and local native runtime/E2E checks appropriate to these changes.
- [x] Obtain an independent review, resolve material issues and report exact local evidence
  alongside GitHub-only checks that remain unobserved until publication.

### Task 5: Additional requested metadata automation

- [x] Add pinned metadata-only PR labeler, trusted base configuration and automatic label
  creation with job-scoped permissions; preserve Release Please lifecycle labels.
- [x] Group ordinary weekly updates under chore(deps), including majors and digests, with
  explicit semantic prefix overrides; document the native separate lock-maintenance branch.
- [x] Verify existing pyproject/uv.lock synchronization through live Release Please evidence,
  preserve frozen validation/bump rules, and validate the added configuration.

## Execution record

- Work is local on `codex/ci-quality-security`, based on `255b7a5`; no product,
  public catalog or immutable compatibility fixtures changed.
- Baseline release/CI behavior: 41 tests passed in the Dev Container before edits.
- Policy tests: 48 title/extractor cases and 46 advisory/release-dispatch cases passed.
  The title, summary, queue-scope, advisory and registry tests were first observed RED.
- Full official Renovate schema validation passed. Tests enforce official action identities
  and full SHA pins without preventing legitimate Renovate pin updates.
- Ruff, format, strict source mypy, generated documentation and wheel/sdist build passed.
- Actionlint and zizmor passed. Queue suppression is exact and backed by a location guard;
  shell issues, checkout credential persistence and implicit Node caching were corrected.
- Independent whole-change review found one material issue: local containerd could not export
  a pulled child digest. A real read-only probe reproduced it. Trivy registry mode fixes it
  without changing the local archive path or image promotion; regression tests passed.
- The real public index `sha256:2d850c0b67527210d4b6b610f12eb700947a0b0c5d64032ed2ec6a9ca278bdaa`
  was scanned through both immutable child digests. Both scans completed with 163 SBOM
  components, no secrets and no fixable HIGH/CRITICAL findings. Each retains 2 CRITICAL
  and 36 HIGH findings without a fixed version; the existing enforcement policy is preserved.
- The existing native amd64 runtime also passed the local archive scan with `--enforce`.
- Native amd64 E2E against disposable Mealie passed all four transport/protocol combinations:
  312 tool paths (308 positive and 4 expected security rejections), 312 input rejections,
  internal network, no published ports and successful cleanup. Runtime source is unchanged;
  the reused local image reports revision `unknown`, so this is functional evidence only.
- Anonymous advisory access correctly failed closed on shared-egress HTTP403. The public
  advisory query was verified through authenticated read-only `gh`; CI uses its temporary
  read-only token, scoped to the exact endpoint and rejecting redirects.
- GitHub-only execution remains unobserved: CodeQL extraction, dependency-review graph,
  scheduled artifact retrieval, OIDC attestations and Release asset upload. No remote
  commits, images, releases or settings were written by this task.
- Final scanner verification: all 43 cases passed in 344.29s; real registry mode and
  original local archive enforcement both passed. Non-attached scanner startup retains
  redacted logs even when Trivy fails.
- A first whole-suite run was interrupted because the registry fix landed after its test
  modules had been collected. The stable four-worker run completed: 1151 passed and one
  HTTP CLI startup timeout at its unchanged 20-second bound. The same HTTP CLI test passed
  serially with coverage in 19.64s. No production code or test expectation was changed to
  hide it; CI retains its existing serial pytest command. pytest-xdist 3.8.0 was used only
  as a temporary Dev Container verification tool, with the same locked pytest 9.2.0.
- Compatibility evidence passed all 78 positive and 78 negative tool paths, with 96.01%
  line coverage and 87.56% branch coverage. The raw parallel failure and serial retest
  reports remain separate in artifacts; no JUnit failure was rewritten as a pass.
- The user additionally requested PR labels and a single weekly dependency update group.
  These metadata/config changes passed workflow lint, Renovate schema validation, a focused
  48-case policy suite and an independent review. No material issue was reported.
- Read-only verification of live Release Please PR2 (head
  `9a6832f539c78a75d5980fcb4aa4eba5caf884e4`) confirms both pyproject and the editable package
  in uv.lock change from 0.1.0 to 0.2.0; both native checks passed. Existing TOML extra-files
  synchronization is retained, as are frozen sync, offline lock validation and bump rules.
