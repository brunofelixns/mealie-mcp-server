# Release PR implementation plan

> **For agentic workers:** Use superpowers:executing-plans for implementation.

**Goal:** Protected main, accumulated release proposal, automatic tested GHCR
publication when the user merges the release PR.

**Architecture:** Python prepares a proposal on a reserved branch. Native checks
gate every PR and final publication. No CI job writes commits directly to main.

**Tech Stack:** Python/uv in Dev Container; Git, gh, jq, Docker and GitHub Actions.

**Spec:** [Design](../specs/2026-11-02-automatic-versioning-design.md).

## Global constraints and review focus

- No Node, local publishing scripts or changes to immutable fixtures.
- Major for breaking changes, minor for feat/fix, patch otherwise.
- Both native checks required, including admins; zero extra approvals for solo use.
- No stale proposal overwrites, CI skip directives, recursive releases or main pushes.
- Dispatch bot-created PR checks explicitly; preserve immutable version tags.

## Tasks

- [x] Reuse and test version preparation, bundle reproducibility and aligned files.
- [x] Anchor after a squash release rather than incrementing from its own merge.
- [x] Identify only owned merged release PRs as publication triggers.
- [x] Maintain one release PR, serializing updates and dispatching its native checks.
- [x] Publish exact tested images and only a Git tag, with main protected.
- [x] Review independently and fix CI skip and stale proposal race findings.
- [x] Verify local directed tests, lint/types/docs and actionlint (37 directed cases;
  the revised complete suite is also required on the implementation PR).
- [x] Apply/verify main protection and permission to create automated PRs.
- [ ] Deliver implementation through a checked PR, then verify the automatic release
  PR exists and its checks are green. Leave its merge to the user.

## Execution record

The initial direct-main design was committed as 23faf2d. Its run 41443352034 was
cancelled before publication when the user requested the PR-based workflow. Main
remained at 23faf2d; Python/GHCR version stayed 0.1.0. That earlier local suite
passed 1005 tests, compatibility 78/78, coverage 96.01%/87.56%, and disposable
Mealie E2E, but is not evidence of the revised hosted PR workflow.

Review found and tests reproduced that skip-ci proposal commits could suppress
publication after merging; removed skip directives. Proposal jobs now serialize
with a repository-wide group to prevent an old run replacing a newer proposal.
The reviewer confirmed both fixes. Final verification must use actual GitHub PRs,
required checks, branch settings and the bot-created release proposal.
