---
name: mealie
description: Use when working with recipes, ingredients, recipe organization, meal plans, or shopping lists in Mealie through mealie-mcp-server.
license: MIT
metadata:
  version: "1.0"
---

# Work with Mealie

Turn the user's request into a workflow across the connected Mealie tools. The
model interprets recipe language and makes proposals; the server looks up data
and performs deterministic mutations. Keep the user's language in the response.
Requires a connected `mealie-mcp-server`; the client supplies the model. No local
scripts or additional API keys are needed to use this skill.

## Choose the workflow

Read only the reference needed for the current task:

- Import, inspect, structure, classify, or edit recipes:
  [Recipe maintenance](references/recipes.md).
- Build or change a menu, including the existing `weekly-meal-plan` prompt:
  [Meal planning](references/meal-planning.md).
- Generate or edit the shopping list, including shopping from a menu:
  [Shopping lists](references/shopping.md).

For a combined menu-and-shopping request, read the planning reference first and
the shopping reference when preparing the shopping stage.

## Work within the request

Check that the connected server exposes the tools needed for the chosen workflow.
Use their current input schemas and the server's instructions; do not guess tool
prefixes, IDs, argument names, or capabilities. A manually installed skill does
not configure the MCP connection or grant permission to change Mealie.

Keep read-only requests read-only. A proposal is not permission to save it.
When the user authorizes concrete changes, carry them out within that scope;
reuse any confirmation already given for the same changes. Ask only for missing
information or authorization that affects the requested operation.

Use compact recipe reads for discovery and detailed reads for faithful edits.
Follow pagination instead of treating the first page as the entire collection.
Prefer a suitable batch operation when it represents the requested work.

After mutations, inspect the returned result and verify the affected state when
the tool does not already return verified state. Batch results may be partial:
report successes, failures, and anything whose outcome remains unknown separately.
Do not automatically repeat a write. After a timeout, cancellation, or ambiguous
failure, read the affected records before deciding how to recover. Never replay
successful batch entries as part of recovery.

Report what was found or changed using recipe names, dates, or list names that
the user recognizes. Include unresolved choices and partial failures without
claiming that proposed work was saved.
