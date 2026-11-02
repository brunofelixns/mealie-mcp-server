# Automatic GHCR CI Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Retire local publication tooling, verify every push/PR, publish tested amd64/arm64 images after successful main-branch checks, and make `brunofelixns/mealie-mcp-server` public.

**Architecture:** A single GitHub Actions workflow runs the existing Linux Dev Container checks on native amd64 and arm64 runners. Each successful check job exports its exact tested runtime and image identity as a short-lived artifact. A dependent publisher, restricted to main pushes and granted `packages: write`, loads and verifies both artifacts, pushes commit-specific architecture tags, verifies the multiarch manifest, and updates `latest`. Authentication uses `GITHUB_TOKEN`; no local publication command or PAT is required.

**Scope decisions:** PRs and other branches validate without publishing. Main pushes produce `latest` and `sha-<full-commit>` tags; existing version tags are not overwritten. The user explicitly authorized making the code public and uploading to this repository's GHCR namespace. Existing skills changes belong to this chat and are included in the published source. Repository visibility is distinct from existing package visibility.

## Tasks

- [x] Verify the remote, admin access, current branch, pending changes, action revisions, and package association.
- [x] Add failing behavioral tests for workflow publication gates and the actual publisher shell's success/failure behavior.
- [x] Replace the workflows; remove local publication scripts, their dedicated tests/runbooks, and obsolete active links. Preserve general Docker builds, tests, security scanning, and migration evidence.
- [x] Validate syntax, shell behavior, docs, compatibility, and builds in Linux; review the patch and check tracked content before public visibility.
- [ ] Commit the requested source, make the repository public, push main, observe real Actions, and verify the resulting GHCR manifest or resolve actual failures.

## Review Focus

- No publication from PRs, forks, failed checks, or other branches.
- Both native architectures and real Mealie E2E tests must pass before registry writes.
- Publish the exact tested runtime artifacts, without a second build.
- Validate loaded identities and remote platform digests; update latest only after the commit manifest passes.
- Remove obsolete operational instructions without rewriting immutable reference captures or claiming historical local checks were remote evidence.

## Evidence

- GitHub reports a private repository, main as default, admin access, enabled Actions, and a GHCR package linked to this repository. Local HEAD matches origin/main; pending skills changes are from this chat.
- Skills changes were verified with 27 targeted Linux tests and committed separately as `a56aba3`.
- The new workflow tests first failed against the old configuration. Six behavioral cases now pass, covering the main-push gate and actual publisher shell success, wrong identity/platform, failed push, and wrong manifest.
- Fifteen targeted CI/docs/deployment tests passed; Ruff, formatting, strict mypy, generated docs, wheel/sdist builds, actionlint 1.7.12, and 273 local documentation links passed. Independent review found no blocking issue.
- The local scan passed the retained policy: zero secrets and zero fixable HIGH/CRITICAL findings. Its report still contains unfixed findings (2 CRITICAL, 36 HIGH); passing this policy is not a vulnerability-free claim.
- Basic tracked-file/history checks found no environment credential files or common token/private-key patterns. This was a publication preflight, not an exhaustive security audit.
- Repository visibility was changed to public and anonymous HTTP access returned 200. Main was pushed and Actions run41435854324 started on both native architectures.
- The first hosted run passed974 tests per platform but failed10 container setups: the hosted Docker daemon uses API1.48, while `image inspect --platform` requires1.49. Publication remained skipped. The failure was reproduced locally with `DOCKER_API_VERSION=1.48`; inspection now checks the actual OS/architecture without that optional selector, with regression cases for both valid architectures and mismatches.
- The local disposable Mealie integration passed all four transport/protocol combinations and cleanup, covering312 tool paths and312 input rejections.
- The Docker API1.48 correction passed10 runtime container tests and10 CI/platform regression tests. Image export with the scanner's `--platform` option also succeeded with API1.48. Existing OS/architecture and hardening assertions remain enforced.
