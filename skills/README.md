# Mealie skill

[English](README.md) · [Documentación en español](../docs/skills.md)

The portable [`mealie/`](mealie/SKILL.md) folder teaches an assistant to use this
MCP for recipe maintenance, meal planning, and shopping. Its references are loaded
only when needed. There are two ways to use the same files:

| Method | Use it when | What you need |
|---|---|---|
| Served by MCP | Your client supports `io.modelcontextprotocol/skills` | Connect to a server built from this source and select `mealie`. |
| Manual installation | Your client discovers local Agent Skills | Copy the complete `mealie` folder into its skills directory and configure the MCP connection separately. |

## Served by MCP

The server advertises the extension on modern MCP connections (`2026-07-28`).
Clients discover metadata and the complete SHA-256 file manifest with
`skills/list`, or retrieve it directly using `skills/get` with
`skill://mealie/SKILL.md`. Read the skill and its references with `resources/read`.
The client controls selection, verification, and activation. Reading a resource
alone does not activate a skill. The optional `resources/directory/read` method
is not advertised; discover supporting files through the complete manifest.

The extension works over stdio and authenticated Streamable HTTP. Clients using
the older `2025-11-25` protocol can still read the ordinary skill resources, but
cannot use the extension's discovery methods. Local-skill support does not imply
support for skills served over MCP; consult your client's documentation.

This feature is in the current source. Rebuild the package/image to serve it;
an already-published `0.1.0` image is not updated by a local source change.
See [the detailed protocol example and compatibility notes](../docs/skills.md).

## Manual installation

For Codex, the personal directory is `~/.agents/skills`. Run the following from
the repository root, only if a `mealie` skill is not already installed:

```bash
mkdir -p ~/.agents/skills
cp -R skills/mealie ~/.agents/skills/mealie
```

On Windows, copying these Markdown files does not require Python or Node:

```powershell
$skillsDestination = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Force -Path $skillsDestination | Out-Null
if (Test-Path -LiteralPath (Join-Path $skillsDestination 'mealie')) {
    throw 'A mealie skill already exists; review it before replacing it.'
}
Copy-Item -LiteralPath '.\skills\mealie' -Destination $skillsDestination -Recurse
```

For a repository-scoped Codex installation, copy it into that repository's
`.agents/skills/mealie/`. For another Agent Skills client, use its documented
installation location. Copy the whole folder, including `references/`.

Open a new session if the client has not refreshed skill discovery. In Codex,
invoke `$mealie`, for example: `Use $mealie to propose dinners for next week`.
Configure the [MCP connection](../docs/clients.md) separately; the skill neither
starts the server nor stores credentials. Keep the manual copy aligned with the
server version. To update, review the installed folder and replace it as a whole;
merging files can leave obsolete references behind. Avoid installing multiple
copies of the same skill in active discovery locations.

## Maintain one source

Edit `skills/mealie/`. The wheel build copies this folder under
`mealie_mcp_server/resources/skills/`; the source distribution and Docker build
also include it. Editable source checkouts use the canonical folder directly.
Never edit a build's generated copy. Tests compare every served file's bytes,
digest, size, and frontmatter against this folder, including installed images
without a source mount. The original 78 tools and weekly prompt remain intact.

Sources: [MCP Skills extension](https://modelcontextprotocol.io/extensions/skills/overview),
[Agent Skills format](https://agentskills.io/specification),
[Codex skills](https://developers.openai.com/codex/skills/).
