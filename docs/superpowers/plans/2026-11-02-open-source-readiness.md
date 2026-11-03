# Open source readiness implementation plan

**Goal:** Complete the contributor-facing files and enforce the existing CodeQL
analyses alongside native CI checks, as requested after the repository review.

**Architecture:** Keep the current Python CI and Renovate configuration. Add
GitHub-native issue forms and a PR template; manage repository security settings
separately from versioned configuration. No application or dependency changes.

**Constraints:** Python, tests, documentation generation, and builds run only in
the Linux Dev Container. Preserve immutable fixtures and the public MCP contract.
Do not publish packages/images or merge main. PyPI publication remains optional
and is outside this change without an agreed destination.

- [x] Add SECURITY.md, CODE_OF_CONDUCT.md, bug/feature forms, security contact
  link, and PR template. Update contributor links in both README languages.
- [x] Extend docs/main-protection.json and the CI/contribution guides to name
  Verify amd64, Verify arm64, Analyze python, and Analyze actions.
- [x] Apply and verify the four required checks in GitHub; preserve existing
  protection settings and zero mandatory third-party approvals.
- [x] Enable push protection and verify private vulnerability reporting.
- [x] Verify Renovate installation and repository scope. Do not grant new App
  access without any confirmation required by the browser confirmation policy.
- [x] Run documentation generation/check and relevant existing CI tests in the
  Dev Container, then check the complete diff.

## Verification and operational notes

GitHub's branch API confirms all four required checks, each bound to Actions
(app_id 15368). The browser confirms the existing PR, strict freshness,
conversation resolution, linear history, administrator enforcement, and
force-push/deletion restrictions were preserved. Push protection was enabled;
private vulnerability reporting was already enabled.

The terminal cannot access Docker Desktop's Linux daemon (access denied), so
Dev Container checks cannot yet run. Local .git is read-only: branch creation
failed. Changes remain uncommitted; no main commit or remote publication was made.
The documentation generator/check, workflow lint, and relevant existing CI and
Renovate tests were attempted through Compose; Docker access failed before they
could execute. `git diff --check` passed. JSON parsing of the protection file
succeeded. No runtime behavior changed and no baseline was modified.

Renovate is absent from the repository's installed Apps. Its official installation
form is prepared for exactly brunofelixns/mealie-mcp-server, awaiting action-time
confirmation because it grants write access to code and workflows. Installation
and the first successful Renovate run are not complete.

## Review focus

Avoid soliciting secrets or real recipe bodies in public forms. Use no invented
private email, support SLA, or unsupported version promise. Keep the native
workflow job names aligned with required check contexts. Distinguish completed
CodeQL execution from a policy prohibiting all security findings. Do not claim
that versioned files alone activate GitHub settings or Renovate.

Follow-up 2026-11-03: the Dev Container checks became available through the
authorized Docker launcher. Documentation generation, workflow linters and the
complete ordinary suite passed as part of the recipe review-fix validation;
see `docs/testing/mealie-3.30-evidence.md`. GitHub's branch API again confirmed
the four required checks, strict freshness, linear history and conversation
resolution. The earlier access failure above is historical. Renovate App
installation remains outside this PR and is not claimed complete.
