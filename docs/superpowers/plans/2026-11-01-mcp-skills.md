# MCP Skills Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Serve the Mealie skill through the official MCP Skills extension and ship the same files for manual installation.

**Architecture:** Keep the canonical, portable skill in `skills/mealie/`. Register FastMCP 4.1.4's native `SkillsDirectoryProvider` and `SkillsExtension`; use its byte-preserving resources, manifests, validation, pagination, and protocol negotiation. Include the canonical folder in wheels, source distributions, and runtime images. Existing tool definitions, prompts, server instructions, and compatibility fixtures remain unchanged.

**Scope decisions:** One `mealie` entrypoint routes to recipe maintenance, meal planning, and shopping references. The optional directory-read method is not advertised or implemented. MCP clients control loading and approval; serving content does not activate it. Work proceeds inline in the clean, already-mounted checkout so all Python execution uses the existing Linux Dev Container.

## Tasks

- [x] Add behavioral tests for discovery, direct lookup, resources, byte integrity, invalid URIs, modern/legacy clients, and no Mealie calls. Observe the missing-feature failure.
- [x] Add the canonical skill and register the native provider/extension. Keep manual and served content identical. Run targeted tests.
- [x] Package the folder into wheel/sdist and Docker. Test the installed runtime without source mounts over stdio and authenticated HTTP.
- [x] Document the remote and manual paths, skill selection, client limitations, and intentional additive compatibility changes. Link English and Spanish landing pages.
- [x] Regenerate documentation. Run formatting, lint, typing, the full coverage suite, compatibility checks, and package builds in Linux. Review the finished patch.

## Review Focus

- Complete manifests must cover the exact raw bytes returned, including references and non-ASCII characters.
- Unknown skill/resource and traversal attempts must fail rather than expose arbitrary filesystem content.
- Legacy clients must retain tool/prompt behavior and be able to read ordinary skill resources without the extension.
- Installed wheels and images must include the skills independently of the checkout and working directory.
- The immutable baseline remains intact; additive resources and modern extension capability are checked explicitly as a documented difference.

## Execution evidence

- The existing Dev Container was started; FastMCP 4.1.4 includes the native experimental Skills extension.
- The new discovery test first failed because the server did not advertise `io.modelcontextprotocol/skills`; 26 targeted tests passed after implementation.
- Ruling: Move `CatalogOrder` to the local tool provider, since the native extension rejects server-wide transforms. The original tool catalog/order tests remain strict.
- Independent review identified a supporting-file link that resolved incorrectly from the skill root. A regression test reproduced it; the reference now names the skill-root path explicitly.
- The skill passed `skill-creator` validation. Wheel and sdist preserved all five files under `skills/` byte for byte; 134 local documentation links were checked.
- Final Linux suite: **1016 passed, 4 live tests deselected**, in 427.41 seconds. This includes the installed runtime's Skills methods/resources over stdio and authenticated HTTP without source mounts. HTTP tests explicitly allow their disposable container hostname, retaining the normal Host protection.
- `scripts/check_compatibility.py --require-all --coverage-json artifacts/coverage.json --junit-xml artifacts/pytest.xml` passed: all 78 positive and 78 negative tool paths have execution evidence. Line coverage was 96.01%, branch coverage 87.56%; the new Skills registration module had 100% line/branch coverage.
- Ruff, format, strict mypy, generated-doc checks, wheel/sdist builds, local runtime build, and `git diff --check` passed. The immutable fixtures, curated catalog, original instructions, weekly prompt, and dependency lock were not edited. No remote publication or live-provider validation was performed.
