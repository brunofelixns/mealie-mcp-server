# Complete recipe tools implementation plan

**Goal:** Implement the recipe gaps approved after the repository/API analysis: notes first, metadata, comments, assets, native import/export, sharing and cooking history, with tests and documentation.

**Architecture:** Preserve the original 78 tools and their immutable fixtures unchanged. Append strict, explicitly registered tools to the public catalog. Keep domain services independent of MCP, use the lifespan Mealie client, and check writes without automatic retries.

**Tech stack:** Existing Python, FastMCP, Pydantic, HTTPX2 and pytest, executed only in the Linux Dev Container. API reference: Mealie v3.29.0, matching integration Compose.

## Constraints and decisions

- The user's implementation request approves the scope and notes approach described in the previous analysis. No release, remote commit, production write or deployment is included.
- Work on local branch `codex/complete-recipe-tools`; preserve pre-existing uncommitted open-source-readiness changes.
- Keep baseline tools byte-for-byte equivalent in their public definitions. New functionality uses additional tools rather than broadening the legacy patch schema.
- Preserve omission/null/zero/false/empty arrays, unknown provider fields and collection order. Strict nested models retain original camelCase aliases.
- Notes use stable `referenceId`, not array indexes. Addition appends, editing retains identity, deletion refuses linked notes unless reference removal is explicitly requested. Check `expectedUpdatedAt` before recipe read-modify-write; this detects stale snapshots but is not an atomic provider lock.
- Recipe metadata updates merge nested nutrition/settings/extras into the latest recipe rather than resetting omitted fields. Verify requested changes after writing; report verification failure and avoid unsafe automatic write replay.
- Comments, share tokens, timeline entries and imports use their dedicated Mealie endpoints and preserve provider errors/permissions. Signed URLs and recipe/file contents are never logged.
- Binary responses must remain same-origin, bounded, authenticated and downloadable as base64 MCP results; no arbitrary host file writes. Uploads use bounded base64 data, never host paths.
- Treat provider-specific unsupported operations honestly: use only endpoints present in v3.29.0 and document limits rather than inventing asset deletion or atomic transactions.

## Tasks

### 1. Notes (first deliverable)

Create input models, independent service, explicit tools and unit/MCP behavior tests for `get_recipe_notes`, `add_recipe_note`, `update_recipe_note`, `delete_recipe_note`. Cover stale snapshots, unknown/duplicate IDs, append/order, empty text/title semantics, existing unknown fields, referenced-note deletion, no-op, provider failure/no retries and verification failure. Catalog contribution goes in ignored artifacts for integration by the coordinator.

### 2. Collaboration, sharing and timeline

Create dedicated models, service/tools and unit/MCP tests for recipe comments (list/create/update/delete), share links (list/create/revoke), timeline (list/create/update/delete and image upload). Check exact upstream request shapes, identifiers and ownership behavior; propagate permissions without retrying writes. Work only in family-specific files.

### 3. Assets and native import/export

Create dedicated models, service/tools and unit/MCP tests for asset upload/from URL, native URL/HTML-or-JSON/ZIP imports and recipe export formats/download. Extend the client with bounded binary retrieval without changing JSON request behavior. Validate base64/size/path segments, multipart forms, redirects, content length, timeout and invalid/provider responses. Work only in family-specific files and the binary client extension.

### 4. Metadata and integration

Add `update_recipe_metadata` for prep/cook/perform/total times, yield/servings/name/description/source, nutrition, settings and extras, with required snapshot token and nested merging. Write behavior tests first, then implementation. Integrate all family registrations and catalog contributions. Record extension owners and executed MCP evidence separately from the immutable 78-tool migration baseline; update compatibility checker, documentation generator and catalog-count tests to check both layers.

### 5. Documentation and verification

Document all new operations, examples, note/reference semantics, provider limits, import side effects, binary results and concurrency limitations. Record intentional additions in migration differences, update portable skill/server guidance and regenerate English/Spanish tool listings. Extend disposable real-Mealie scenarios for new tools where possible. Run Ruff, formatting, mypy, documentation check, full tests/coverage/JUnit, compatibility checker, build, container tests and disposable E2E. Review the final diff independently and fix material findings before completion.

## Review focus

- Existing note links must survive edits; explicit linked deletion must remove only the matching reference.
- Nested metadata changes must not reset omitted settings or nutritional fields.
- Ambiguous writes/imports must never be replayed automatically.
- Binary downloads must neither follow an external redirect nor exhaust memory.
- Baseline comparison must still detect regressions in every original tool; new tools need their own positive and rejection MCP evidence.

## Progress

- Baseline: 66 focused recipe/core organizer tests passed during analysis; documentation matches original 78-tool catalog.
- Implementation started on the local feature branch; no original fixtures will be changed.
- Notes, metadata, collaboration and IO implemented and integrated: 102 tools.
- Independent review: fixed bool/number equality, nullable step references,
  provider numeric-null coercion and JSON Schema pagination bounds; regression
  tests cover the material fixes. Original fixtures remain unchanged.
- Ruff, formatting, mypy, workflow checks, docs generation, wheel/sdist and local
  runtime builds completed. Four real-Mealie protocol/transport runs passed:
  408 tool paths, 404 positive operations, four expected SSRF rejections and
  408 argument rejections; owned runtime data cleaned up.
- Full suite: 1,380 passed, three obsolete catalog expectations failed and were
  corrected; affected 11 tests rechecked green. The full suite was not repeated
  after test-only corrections; both JUnit reports are retained. Compatibility
  confirms executed positive/rejection evidence for all 102 tools. Coverage:
  96.10% lines / 87.06% branches. See testing/recipe-extensions-evidence.md.
