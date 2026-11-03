# Edición de recetas, notas y archivos

El MCP conserva las 78 herramientas originales y las 24 de la primera ampliación;
añade 60 para un total de 162. La [guía de Mealie 3.30](mealie-3.30.md) detalla
búsqueda avanzada, sustituciones, descargas, temporizadores, trabajos y recetarios.
Los [esquemas completos](tools.md) describen sus argumentos. La API de referencia
es Mealie **3.30.0**, fijada también en la integración desechable.

## Notas

Las notas de receta tienen `title`, `text` y `referenceId`. Son distintas del
campo `note` de un ingrediente y de los comentarios de usuarios.

1. Consultar `get_recipe_notes({"slug":"mi-receta"})` o `get_recipe_detailed`.
2. Copiar el `updatedAt` actual a `expectedUpdatedAt` de la siguiente escritura.
3. Usar `add_recipe_note`, `update_recipe_note` o `delete_recipe_note`.
4. Para otra escritura, usar el nuevo snapshot de la respuesta o releer.

Ejemplo para `add_recipe_note`:

```json
{
  "slug": "mi-receta",
  "expectedUpdatedAt": "<updatedAt actual>",
  "title": "Conservación",
  "text": "Guardar refrigerado una vez que se enfríe."
}
```

Añadir conserva las notas anteriores y su orden; genera un UUID si no se indica
`referenceId`. Editar o borrar utiliza ese UUID, nunca una posición. Editar cambia
solo el título y/o texto solicitado; las cadenas vacías son válidas. Se conservan
campos desconocidos del proveedor. Si una nota está enlazada desde instrucciones,
su borrado se rechaza salvo que se pida `removeReferences:true`: entonces se quitan
solo esos enlaces y se conserva el resto del paso. Los ID internos de pasos pueden
regenerarse en cualquier actualización y no son identidades estables.

Las escrituras comprueban el snapshot y verifican la respuesta de Mealie, sin
reintentar ni restaurar automáticamente. Ante fallo o respuesta ambigua, releer
antes de otra edición. El snapshot detecta cambios anteriores al GET, pero **no
es un bloqueo atómico** entre GET y PATCH.

## Metadatos y nutrición

`update_recipe_metadata` requiere `slug` y `expectedUpdatedAt`. Admite nombre,
descripción, `orgURL`, raciones/rendimiento, `totalTime`, `prepTime`, `cookTime`,
`performTime`, `nutrition`, `settings` y `extras`.

```json
{
  "slug": "mi-receta",
  "expectedUpdatedAt": "<updatedAt actual>",
  "prepTime": "10 minutes",
  "cookTime": "20 minutes",
  "nutrition": {"calories": "250", "proteinContent": "12"},
  "settings": {"showNutrition": true},
  "extras": {"procedencia": "cuaderno familiar"}
}
```

Los objetos se combinan con el estado actual: cambiar calorías no borra proteínas,
y cambiar `showNutrition` no altera visibilidad. Omitir conserva; `nutrition:null`
elimina el bloque y un campo nutricional `null` lo vacía. Mealie almacena nutrición
como cadenas, incluido `"0"`; no se calculan ni inventan valores. Se conservan
`false`, cero y cadenas vacías cuando el campo los admite.
Raciones y cantidad de rendimiento admiten cero y rechazan `null` antes de llamar
a Mealie, que lo convertiría en cero y no conservaría la distinción solicitada.

`extras` combina claves; `removeExtraKeys` borra solo las indicadas. Una clave no
puede añadirse y eliminarse a la vez. Opciones: `public`, `locked`, `showNutrition`,
`showAssets`, `landscapeView`, `disableComments`. Cambiar privacidad o bloqueo
requiere petición expresa del usuario. `patch_recipe` conserva el contrato legado;
los campos adicionales se editan con la nueva herramienta.

## Comentarios, compartir e historial

| Uso | Herramientas |
|---|---|
| Comentarios | `get_recipe_comments`, `create_recipe_comment`, `update_recipe_comment`, `delete_recipe_comment` |
| Compartir | `get_recipe_share_links`, `create_recipe_share_link`, `delete_recipe_share_link` |
| Historial | `get_recipe_timeline`, `create_recipe_timeline_event`, `update_recipe_timeline_event`, `delete_recipe_timeline_event`, `set_recipe_timeline_event_image` |

Las operaciones usan el usuario del token y los permisos de Mealie. Editar/borrar
comentarios ajenos requiere administrador; los comentarios vacíos se rechazan.
Los tokens compartidos permiten acceder a quien los tenga: no crearlos ni
difundirlos como efecto secundario de otra tarea. Sin `expiresAt`, Mealie 3.29
aplica su caducidad predeterminada de 30 días; borrar el token revoca el acceso.

El historial admite paginación, texto e imagen. Mealie no permite cambiar tipo
ni fecha de un evento existente mediante la edición. Los `null` de `eventMessage`
y `image` pueden ignorarse por `exclude_defaults` del proveedor; para vaciar el
mensaje se puede usar `""`. No hay borrado dedicado de la imagen del evento.

## Adjuntos e importación/exportación

`upload_recipe_asset` carga nombre, icono, extensión y `fileBase64`.
`create_recipe_asset_from_url` importa una imagen mediante Mealie, sujeto a sus
restricciones de red. Los adjuntos se consultan en `get_recipe_detailed`; la API
de referencia no ofrece borrado físico dedicado de un adjunto.

`import_recipe_from_url`, `import_recipe_from_html_or_json` e
`import_recipe_from_zip` usan los importadores nativos y devuelven el slug creado.
HTML/JSON admite schema.org Recipe como cadena. `includeTags`/`includeCategories`
controlan la taxonomía cuando el endpoint las admite. Importar puede crear recetas
y organizadores: comprobar el resultado antes de repetir una respuesta ambigua.
El flujo manual con `create_recipe` sigue disponible. Los imports IA opcionales
de Mealie 3.30 se explican en la [guía de adaptación](mealie-3.30.md); utilizan la
configuración del proveedor, sin añadir un modelo local.

`get_recipe_export_formats` descubre plantillas; `export_recipe` recibe
`templateName` y devuelve `filename`, `mediaType`, `size`, `dataBase64`. No escribe
archivos del host; el cliente puede decodificar y guardar donde el usuario elija.

Límites: imágenes/adjuntos 10 MiB; HTML/JSON 2 MiB UTF-8; ZIP/exportación 20 MiB.
ZIP limita 1.000 entradas y 100 MiB declarados expandidos, rechazando rutas
inseguras y entradas cifradas. Las descargas tienen límite de bytes, permanecen
en el origen Mealie y rechazan compresión. No se registran cuerpos, secretos ni
URLs firmadas. HTTP mantiene además su límite global de petición.

## Pruebas

Las pruebas unitarias cubren conservación, errores y límites; cada herramienta
tiene un contrato MCP positivo y un rechazo sin efectos secundarios. El checker
compara el prefijo original con los fixtures inmutables y exige evidencia Python
para las adiciones. Los [E2E desechables](testing/local-e2e.md) ejercitan el catálogo
por stdio/HTTP y ambos protocolos sin usar credenciales personales.
La [evidencia local de esta ampliación](testing/recipe-extensions-evidence.md)
distingue esas comprobaciones de una publicación o despliegue.
