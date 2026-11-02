# Skills de Mealie: por MCP o instalación manual

[English guide](../skills/README.md) · [Índice](README.md)

El skill [`mealie`](../skills/mealie/SKILL.md) contiene procedimientos para usar
las herramientas existentes. El asistente interpreta la petición; el servidor
consulta y modifica Mealie. Los skills no ejecutan un LLM dentro del servidor,
configuran credenciales ni autorizan escrituras por sí mismos.

## Contenido y ubicación

La fuente única es [`skills/mealie/`](../skills/mealie/SKILL.md):

| Archivo | Cuándo se utiliza |
|---|---|
| [SKILL.md](../skills/mealie/SKILL.md) | Selección del flujo, alcance, lectura y recuperación de operaciones. |
| [references/recipes.md](../skills/mealie/references/recipes.md) | Importar, estructurar ingredientes, editar instrucciones y organizar recetas. |
| [references/meal-planning.md](../skills/mealie/references/meal-planning.md) | Consultar el plan existente, proponer un menú y guardar lo confirmado. |
| [references/shopping.md](../skills/mealie/references/shopping.md) | Preparar compra, enlazar recetas y evitar duplicar cantidades. |

Se empieza con un único skill con referencias por tarea. No es necesario cargar
todas las guías para una petición. El contenido está en inglés para facilitar
su reutilización; el skill indica responder en el idioma del usuario.

## Vía 1: skills servidos directamente por MCP

Al construir el servidor desde este código, `create_server` registra
`SkillsDirectoryProvider(experimental_skills=True, supporting_files="resources")`
y `SkillsExtension` de FastMCP 4.1.4. Se utiliza su implementación nativa de la
extensión oficial `io.modelcontextprotocol/skills` (SEP-2640). FastMCP todavía
la identifica como experimental. No se añaden herramientas al catálogo de78.

En MCP `2026-07-28`, `server/discover` anuncia estas capacidades (extracto):

```json
{
  "resources": {"subscribe": false, "listChanged": false},
  "extensions": {
    "io.modelcontextprotocol/skills": {}
  }
}
```

El servidor también conserva sus demás capacidades. El objeto vacío significa
que no se ofrece la operación opcional `resources/directory/read`.

El flujo del cliente es:

1. Consultar `server/discover` y comprobar la extensión.
2. Usar `skills/list` para descubrir `mealie`, o `skills/get` con
   `uri: "skill://mealie/SKILL.md"` si ya conoce su URI.
3. Conservar la entrada completa: `frontmatter` y `resources`, con URI,
   `digest` SHA-256 y `size` en bytes de cada archivo. Los resultados incluyen
   `resultType`, `ttlMs` y `cacheScope`; el cliente respeta `nextCursor` si aparece.
4. Cuando corresponda cargar el skill, leer su archivo con `resources/read`.
   Leer las referencias por sus URI solo cuando se necesiten, por ejemplo
   `skill://mealie/references/recipes.md`.
5. Comprobar bytes, hashes y frontmatter conforme a la especificación y aplicar
   el proceso de activación/aprobación del cliente. Una lectura ordinaria no
   activa el skill. Si cambia el manifiesto, refrescarlo antes de reutilizarlo.

Los archivos son los mismos para stdio y HTTP. HTTP requiere el Bearer del MCP
también para listar skills y leer referencias. No se utiliza la API key de Mealie
como token de acceso al MCP. Ninguna de estas lecturas consulta ni modifica Mealie.

### Ejemplo con un cliente compatible

Este ejemplo usa FastMCP 4.1.4 como cliente Python y negocia la extensión
explícitamente. Es una consulta de comprobación; no instala ni activa el skill:

```python
import asyncio
import os

from fastmcp import Client
from fastmcp.skills import SkillsClientExtension


async def main():
    async with Client(
        "https://mcp.example.com/mcp",
        auth=os.environ["MCP_AUTH_TOKEN"],
        extensions=[SkillsClientExtension()],
    ) as client:
        entries = await client.list_skills()
        entry = await client.get_skill("skill://mealie/SKILL.md")
        content = await client.read_resource(entry.uri)
        print([skill.frontmatter.name for skill in entries])
        print(content[0].text)


asyncio.run(main())
```

El SDK añade los metadatos `_meta` requeridos por el protocolo. Para stdio, usar
el transporte de proceso del cliente con el comando ya documentado en
[Clientes](clients.md); los métodos y URI son idénticos.

### Compatibilidad y límites

MCP `2025-11-25` conserva las herramientas y el prompt existentes. Puede listar
y leer los archivos como recursos ordinarios; no negocia `skills/list` ni
`skills/get`. Un cliente moderno sin soporte de la extensión también puede leer
recursos, pero no debe tratarlos automáticamente como skills activados.

Que un cliente admita skills locales no demuestra que admita skills por MCP.
Comprobar la [matriz de clientes](https://modelcontextprotocol.io/clients) y la
documentación del cliente. Las pruebas del proyecto verifican el servidor con
FastMCP por stdio/HTTP; no constituyen prueba de activación en cada aplicación.

URI de skill o archivo desconocidos y rutas que intentan salir de la carpeta
se rechazan con `-32602`. El manifiesto oficial no incluye `_manifest`: este
último es un recurso auxiliar de FastMCP que también puede aparecer en
`resources/list`. La fuente de integridad de la extensión es `skills/list/get`.

Esta funcionalidad corresponde al código actual. Para tenerla en un servidor
instalado hay que reconstruir el wheel o la imagen con este código y actualizar
el despliegue. Una compilación local no cambia la imagen `0.1.0` ya publicada.
Seguir [Contenedores](containers.md); publicar una nueva imagen es una operación
separada.

## Vía 2: instalación manual

Copiar la carpeta completa `skills/mealie`, con `SKILL.md` y `references/`, a la
ubicación de skills de tu cliente. El servidor puede seguir conectado mediante
stdio o HTTP: esta vía no requiere que el cliente implemente SEP-2640.

Para Codex, instalar a nivel personal en `~/.agents/skills/mealie/` o a nivel de
repositorio en `.agents/skills/mealie/`. Los [comandos Bash y PowerShell](../skills/README.md#manual-installation)
crean la copia sin ejecutar Python ni instalar Node en el host. Si ya existe un
skill con ese nombre, revisarlo antes de sustituirlo. No mezclar una versión nueva
con archivos obsoletos ni mantener varias copias activas del mismo skill.

Después de configurar por separado la [conexión MCP](clients.md), abrir una
sesión nueva si el cliente no actualiza el descubrimiento. En Codex, invocar
`$mealie`; por ejemplo:

```text
Usa $mealie para revisar las recetas con ingredientes pendientes de estructurar.
Muéstrame la propuesta antes de cambiarlas.
```

Para otros clientes, utilizar su instalación e invocación documentadas. No copiar
tokens a `SKILL.md` ni a sus referencias. Mantener la copia manual alineada con
la versión del servidor. Si un cliente admite las dos vías, elegir una para
cargar este skill y evitar registros duplicados.

## Mantenimiento y comprobaciones

Editar solo `skills/mealie/`. Hatch incluye esos archivos en el sdist y los copia
al wheel bajo `mealie_mcp_server/resources/skills/`; Docker construye e instala
ese wheel. La copia empaquetada es un artefacto de build. En un checkout editable
se usa la carpeta fuente cuando no existe una copia empaquetada.

Las pruebas comparan frontmatter, manifiesto, tamaños, hashes y bytes servidos
con la fuente manual. También cubren URI inválidas, autenticación HTTP, clientes
modernos/legacy y la imagen instalada sin montar el código. Ejecutar los
[checks de desarrollo](development.md); los cambios aditivos están registrados
como [D12](migration/differences.md#d12-skills-distribuidos-por-mcp-y-como-archivos-portables).

Referencias: [extensión oficial](https://modelcontextprotocol.io/extensions/skills/overview),
[especificación de Skills](https://skills.extensions.modelcontextprotocol.io/specification/beta/skills),
[formato Agent Skills](https://agentskills.io/specification) y
[skills de Codex](https://developers.openai.com/codex/skills/).
