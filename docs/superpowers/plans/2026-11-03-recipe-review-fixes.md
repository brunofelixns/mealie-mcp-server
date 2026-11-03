# Recipe review fixes implementation plan

> **For agentic workers:** Use test-driven development and focused parallel tasks; retain this plan as the execution ledger.

**Goal:** Apply the four accepted review improvements, validate the complete recipe changes and open a PR to `brunofelixns/mealie-mcp-server:main`.

**Approved design:** The user explicitly selected all four recommendations from the preceding review. Keep the Python architecture and current feature branch. Resolve metadata-batch destinations to canonical recipe IDs before any writes and reject duplicate identities. Emit standard JSON Schema numeric bounds while preserving integer input semantics and the original 102 tool definitions except intentional corrections to the 60 new tools. Audit the live disposable provider in the E2E/CI controller and compare a separate, versioned subset of the Mealie 3.30 schema for incompatible field changes. Reject failed, errored or ambiguous JUnit evidence independently of pytest's exit code.

**Alternatives considered:** Reject UUID-looking slugs would exclude valid native identities, so canonical resolution is preferred. Raising timeouts or retrying writes does not solve duplicate mutations and is excluded. A route-only manual audit remains useful but cannot guard schema drift in CI; use a focused provider contract rather than copying or changing historical migration captures.

**Constraints:** Python/tests/builds only in Linux Dev Container; no host runtime or Node. Preserve immutable `tests/fixtures/compatibility`. No write retries. Keep null/omission/false/zero/order and unknown provider fields. Do not print secrets, real recipe bodies or signed URLs. User authorizes committing/pushing all current changes and creating a PR; no merge, release or deployment.

## Tasks

- [x] Metadata batch: reproduce aliases with a failing deterministic test; preflight identity resolution and duplicate rejection before PATCH; retain ordered per-item outcomes and bounded concurrency; test distinct recipes, stale snapshots, failures and cancellation.
- [x] Numeric schema: failing parity tests for all affected new inputs, whole-number floats, bool rejection and boundaries; emit minimum/maximum; regenerate only intended new definitions and docs.
- [x] API audit: persistent failing tests for route/version/type/required-field drift; versioned focused 3.30 contract fixture with provenance; run against actual E2E OpenAPI before mutation scenarios and fail CI through the runner; preserve owned-resource cleanup.
- [x] JUnit gate: failing tests for unrelated failures/errors, duplicate/ambiguous case identities and wrong positive-test class/file; fail closed while accepting clean executed evidence.
- [x] Integrate and document D15, recipe guide, development/CI checks and validation results. Preserve original definitions/captures and verify cross-task behavior.
- [x] Run Ruff/format/mypy/workflow/docs checks, full pytest with coverage/JUnit, compatibility gate, wheel/sdist/runtime build and four real-provider E2E cases; avoid overlapping CPU-heavy E2E with sharded startup tests.
- [x] Independent final review, fix findings and recheck affected behavior.
- [x] Commit all authorized repository changes, push feature branch and open PR against verified main. Confirm remote head/files and report actual CI state without claiming unobserved success.

## Review focus

1. Slug and UUID aliases of one recipe must never cause two writes in the same batch.
2. Preflight failure must not pretend an unissued write has an unknown outcome or replay it.
3. Schema corrections must not silently widen integer coercion or alter immutable baseline tools.
4. Audit drift must fail before recipe mutations and still clean the disposable stack.
5. A passing duplicate test cannot mask a failed or wrongly attributed JUnit case.

## Progress

- Prior work: 162 tools, 1,794 ordinary validated cases, 4/4 Mealie 3.30 E2E; previous raw reports retained under artifacts. These are historical results until this phase is revalidated.
- Existing unrelated readiness files are included because the user explicitly requests uploading all current changes; inspect them and do not overwrite their content.
- Remote base refresh: `origin/main` advanced from `274785f` to Release Please
  commit `b674612` (0.2.0). After the parallel workers finish, checkpoint the
  dirty work with a task-owned stash, advance the uncommitted feature branch to
  that base and restore the work before final validation. This adopts the real
  release files without manually bumping versions or creating an unnecessary
  worktree. Preserve the checkpoint until the complete work is committed.
- Metadata batch: red regression reproduced aliases; targeted implementation
  validated with 114 tests. One bounded identity GET is added per target;
  duplicates abort before all PATCH operations, failed lookups remain ordered
  no-write failures, and distinct targets retain fresh snapshots and partial
  outcomes. New native alias regression is included in the E2E scenario.
- JUnit gate: observed nine failing regressions, then 16 targeted tests passed.
  The stricter attribution also accepts the previous real JUnit (historical
  evidence only). Any failed/errored case or declared failure/error count and
  duplicate identity now invalidates the report; module/function attribution
  binds positive/rejection evidence to its declared tests.
- Numeric corrections: eleven new schemas integrated from the reviewed model
  mapping, with exact assertions preserving the previous 102 definitions.
- Base refresh completed without conflicts: branch now starts at `b674612`;
  checkpoint `37351cc1e5fb6b1f4d48a019bf5946c7c0f07436` is retained in the stash.
  All tracked/untracked work was restored. The 0.2.0 version comes from the
  existing Release Please commit, not a manual version bump.
- Numeric focused validation: 353 tests passed, including 120 new parity/MCP
  cases; Ruff/format/mypy passed. API audit focused validation was initially 52
  cases; final independent review then reproduced an unsupported-validator gap
  (`dependentRequired`). Fourteen new red regressions led to an explicit
  supported-keyword guard. The 59 auditor cases now pass and the native original
  OpenAPI still has no contract errors. This script-only change does not affect
  the installed runtime. A fresh auditor/controller run will supersede those
  modules in the final JUnit after the running full suite completes; all raw
  reports will be retained and no failure will be discarded.
- Independent review rechecked the guard and closed the P2; no important defect
  remains in the reviewed four-improvement scope. Full integrated gates remain
  required before push/PR.
- Static checks on the integrated tree passed: Ruff, format (349 files), mypy
  (110 source files), workflow linters, wheel/sdist and runtime 0.2.0 build.
  Local image uses `revision=unknown` because it contains an uncommitted working
  tree; immutable image ID is `sha256:09cc0487b430ad1984a8991e3cb1c4033839aaa50c7304a39db0c8ac7cec7e24`.
- Final integrated evidence: all 107 files passed in three shards (1,996 cases),
  then the final auditor/controller/cleanup run passed 66 cases, retaining old
  identities and adding 14 regressions. Consolidated JUnit has 2,010 passing
  cases, zero failures; coverage 96.56% lines / 87.35% branches; compatibility
  confirms 162 positives/rejections. Raw reports are retained.
- Native final E2E `mealie-mcp-e2e-ff4b241dc1d3` passed all four cases after the
  real provider audit; 636 positive paths, four SSRF rejections, eight AI config
  rejections, 648 argument rejections and cleanup passed. No configured LLM
  provider, remote CI or native ARM result is claimed by these local checks.
- Feature commit `68c6858dc9e253e3b8eef3e2b4cfd9a8c1965f4f` uploaded all 125
  changed repository files. PR [#7](https://github.com/brunofelixns/mealie-mcp-server/pull/7)
  is open from `codex/complete-recipe-tools` to verified `main` (`b674612`).
  Publication of the PR does not merge it or publish a package/image; hosted
  checks must be assessed separately from the local evidence above.
