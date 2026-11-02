# Release Please App implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** Automatically start required native checks when Release Please updates
its release proposal, using a credential dedicated to this repository.

**Architecture:** A private repository-only App mints a short-lived token for the
official CLI. Verify installation scope before writes; retain GITHUB_TOKEN for
release creation and exact-tag dispatch and retain the human release-merge gate.

**Tech Stack:** Official create-github-app-token v3.3.0 (Node24 only in Release
Please CI), existing official Release Please, Python/uv tests in Dev Container.

**Spec:** [Design](../specs/2026-11-02-release-app-design.md).

## Constraints and review focus

- Two App permissions only: Contents write and Pull Requests write; one repository.
- Token/key absent, empty/wrong/multiple installation repositories: fail before CLI.
- No main bypass, automatic merge, credential logging or host Python/Node runtime.
- App token only in its scope probe and CLI step; revoke at job completion.
- Approval-blocked registration remains pending until explicit user approval.

## Task: Prepare, review and activate the dedicated identity

- [x] Add failing scope-probe behavior cases and workflow token-wiring checks.
- [x] Pin the official action, restrict token scope and switch the CLI token.
- [x] Replace manual-approval instructions with App setup, operation and rotation.
- [x] Pass directed tests, lint, types, lock/docs checks and independent review.
- [ ] Open a protected configuration PR and pass native CI.
- [ ] Obtain explicit approval for the persistent App permission scope.
- [ ] Register/install the App, store its private key, merge the configuration PR.
- [ ] Observe an automatic release-proposal update and native checks; leave PR open.

## Execution record

The new behavior first failed7 cases, then passed41 directed tests after the
workflow change (including HTTP-error scope rejection). Ruff, formatting, mypy83
source files, offline lock validation, generated documentation and actionlint for
the changed release workflow passed in the Linux Dev Container. Independent review
found no blockers. Registration remains unsubmitted
after automatic approval review rejected the original three-permission request.
Primary GitHub labels documentation confirms Pull Requests write suffices, so the
pending form and token request now omit Issues write entirely.
