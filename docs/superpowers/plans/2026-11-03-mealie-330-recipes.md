# Mealie 3.30 recipe completion implementation plan

**Goal:** Complete the recipe capabilities identified by the API audit and adapt the MCP to Mealie 3.30.0, beginning with advanced search, substitutions and media downloads.

**Architecture:** Keep the 102 existing tool definitions, including the immutable 78-tool migration baseline. Add explicit strict tools by family instead of an unrestricted API proxy. Preserve unknown provider data, ordered collections, references and field presence; services stay independent of MCP. Reuse the existing authenticated, bounded HTTP client and lifespan.

**Scope:** The user's request approves the detailed preceding audit. Include recipe search/suggestions, substitutions, native parser, step durations, media downloads, import preview/AI/progress/bulk, recipe bulk deletion/export and reports, cookbooks, favorites/ratings, comment/timeline/share reads, recipe actions and advanced meal-plan entries/rules/random/iCal. General accounts, admin/backups, AI-provider configuration and unrelated infrastructure are outside recipe scope.

## Global constraints

- Python, tests and builds run only in the Linux Dev Container; no Node, host Python, production API mutations, publication or remote commits.
- Continue local branch `codex/complete-recipe-tools`; preserve prior changes and unrelated readiness documentation.
- Fix integration Mealie to 3.30.0 at `sha256:90f83da6f3ab0a421efc827118a556168573930105f13fa3321768f42163d784`.
- No automatic retries of writes. Read-modify-write uses fresh snapshots where provided, preserves unrelated fields and verifies requested values. Snapshot checks are not atomic provider CAS.
- Unknown request fields are rejected. Keep provider camelCase aliases, UUID/path validation, omission/null/0/false/[] distinctions and bounded payloads. Never log secrets, recipe bodies, tokens or signed URLs.
- Additions do not imply implicit semantic decisions: substitutions use explicit food IDs or meaningful text-only notes, native parsing/import AI only run when selected, privacy/external recipe actions only change on explicit operations.
- Equivalent existing batch taxonomy/ingredient/instruction tools remain valid; API aliases or redundant native PUT/PATCH endpoints need not become duplicate user tools. Document the capability matrix accurately rather than claiming universal API coverage.

## Tasks and file ownership

### 1. Advanced recipe data

Own new `models/inputs/recipe_advanced.py`, `services/recipe_advanced.py`, `tools/recipe_advanced.py`, matching unit/contract tests, and the existing ingredient service only for preservation fixes. Tools: `search_recipes`, `get_recipe_suggestions`, `parse_recipe_ingredient`, `parse_recipe_ingredients`, `update_recipe_ingredient_substitutions`, `update_food_substitutions`, `update_recipe_instruction_durations`.

- [x] Write failing behavior tests for query forwarding/filters, parser, substitution identities/preservation, stale writes and duration bounds/null.
- [x] Implement explicit models/services/handlers against the 3.30 schema; preserve existing substitutions when legacy ingredient edits touch continuing rows.
- [x] Run unit tests, then MCP positives/rejections, Ruff and mypy.

### 2. Collections and advanced planning

Own new `recipe_collections` and `mealplan_advanced` input/service/tool modules and their tests. Cover cookbook CRUD, favorites/ratings reads, single comment/timeline/share reads, recipe-action CRUD/trigger; advanced meal-plan entry CRUD with text/recipeScale/endDate, random entries, rules CRUD and iCal where the provider supports it. No invented endpoint/field. Stable strict models and native permission handling; preserve fields when PUT requires complete state.

- [x] Inspect exact 3.30 schemas, write failing native request-shape/behavior tests.
- [x] Implement explicit family registrations and catalog contributions, no central registry edits.
- [x] Run focused unit/MCP positives/rejections, Ruff and mypy.

### 3. Import, progress and bulk jobs

Own new `recipe_jobs` input/service/tool modules, tests and a client SSE method if needed. Implement scrape preview, AI import, URL/HTML/AI progress variants, native bulk URL import plus report lookup, bulk delete/export and export list/download/purge, plus guarded metadata batch editing. Consume SSE with bounded bytes/event count; forward progress through an optional callback so services do not depend on MCP. Do not replay interrupted or ambiguous writes. AI uses the provider's configuration and no local OpenAI credential setup.

- [x] Write failing request-shape/streaming/error/cancellation/limit tests.
- [x] Implement bounded native operations; explicit result validation, confidential errors and no retries.
- [x] Run focused unit/MCP tests and existing client regressions, Ruff and mypy.

### 4. Media, integration and version adaptation

Coordinator owns new `recipe_media` models/services/tools/tests: list assets, download individual assets/hero/timeline images and read/download shared recipes. Resolve media from the configured Mealie origin and existing recipe metadata; no arbitrary URLs/paths or host writes. Reuse bounded binary results. Coordinator integrates catalog fragments, family registrations, owners/examples and docs; upgrades the pinned E2E version and audits current-vs-covered capabilities with explicit partial/equivalent statuses.

- [x] Write failing tests for path/asset validation, size/redirect safety and binary roundtrips.
- [x] Implement media handlers, integrate family contributions while preserving the first 102 definitions.
- [x] Adapt docs/skills/server guidance, record D14 and regenerate both languages.

### 5. End-to-end and final verification

- [x] Extend disposable scenarios for new supported functions and 3.30 preservation, including step timers, substitutions, media, weekly meal plans and native jobs.
- [x] Keep AI-provider-dependent features distinguished from successful native-provider evidence when the disposable provider is deliberately unconfigured; test actual failure propagation and controlled positive provider/SSE behavior.
- [x] Run all existing tests plus new tests, with coverage/JUnit. Parallel file shards may be used with separate coverage/JUnit files and a transparent merge; no tests omitted.
- [x] Run Ruff, formatting, mypy, workflow/doc/compatibility checks, wheel/sdist/runtime builds and installed-container tests.
- [x] Independent review, regression fixes and fresh relevant rechecks; four real-provider transport/protocol scenarios and owned-resource cleanup.

## Review focus

1. Editing old ingredient rows must retain substitutions and unknown fields.
2. Media names/token paths cannot escape their configured origin or asset namespace.
3. Weekly endDate is exactly six days after date; recipeScale/text must survive PUT.
4. SSE progress and cancellation cannot trigger a second import or expose private content.
5. Native bulk jobs are not transactions; partial results and outcome uncertainty must remain explicit.

## Progress

- Baseline: current local catalog 102 tools; prior real-provider validation targeted 3.29.0. This phase upgrades runtime evidence to 3.30.0.
- Plan recorded before implementation; tasks are split into disjoint files for parallel work.
- Final route audit adds current-household recipe data to collections: 162 tools total,
  60 added in this phase. The 283-operation provider schema has 90 scoped recipe/planning
  routes: 84 catalog dependencies and six deliberately distinct alternative batch
  contracts. No scope route remains unclassified; general/public-group administration
  is not claimed as implemented.
- Independent review found cookbook slug/UUID and native generated-slug assumptions;
  both were corrected with behavior tests. A directed follow-up found no remaining
  concrete defect in those fixes or the household read.
- Final Mealie 3.30 integration: four cases passed, 648 tool paths, 636 native positive
  paths, four expected SSRF rejections, eight separately verified AI-configuration
  rejections and 648 input rejections. Owned resources were removed successfully.
- Final ordinary evidence: 1,794 passed cases across 101 files, 162 executed MCP
  positives and 162 rejections, 96.53% lines and 87.21% branches. Two initialize
  timeouts in concurrent execution were resolved by repeating the entire 27-file,
  529-test shard after the other runs ended, without source/expectation changes.
  Raw failures and the completed recheck remain in the final report.
