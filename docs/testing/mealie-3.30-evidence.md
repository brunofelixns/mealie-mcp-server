# Evidencia local de recetas con Mealie 3.30.0

Validación del 2026-11-03, en el Dev Container Linux y Docker Desktop local
`linux/amd64`. Esta fase añade 60 herramientas a las 102 existentes: 162 en total.
Las 102 definiciones anteriores conservan exactamente contenido y orden. Las
capturas originales de `tests/fixtures/compatibility` no se modificaron.

Los apartados D14 siguientes conservan la medición anterior a las cuatro
correcciones de revisión D15. La validación posterior se registra al final; las
imágenes y cifras históricas no se presentan como pruebas del código posterior.

## Proveedor y catálogo

Referencia oficial: [Mealie v3.30.0](https://github.com/mealie-recipes/mealie/releases/tag/v3.30.0).

- Imagen: `ghcr.io/mealie-recipes/mealie:v3.30.0`.
- Digest fijado: `sha256:90f83da6f3ab0a421efc827118a556168573930105f13fa3321768f42163d784`.
- Revisión nativa de la imagen: `9552df62118224a377d9c9b0a62706a62220ab86`.
- OpenAPI obtenido de esa imagen: 283 operaciones.
- [Auditoría reproducible](mealie-3.30-api-audit.json): 90 operaciones en el ámbito
  de recetas/planificación, 84 dependencias directas y seis contratos alternativos.
  Cero rutas del ámbito sin clasificar; cero dependencias del catálogo inexistentes.

El informe incluye hashes de OpenAPI y catálogo. Contar dependencias no demuestra
cobertura de todos los campos o parámetros. Los lotes alternativos tienen sus
propios snapshots, orden, errores y resultados parciales; no son una reproducción
exacta de los PUT/PATCH masivos nativos. La [guía 3.30](../mealie-3.30.md) fija el
alcance y permite repetir el análisis.

| Familia nueva | Herramientas |
|---|---:|
| Búsqueda, sugerencias, parser, sustituciones y temporizadores |7|
| Adjuntos, imágenes y lectura/descarga compartida |6|
| Recetarios, consultas personales, colaboración, acciones y hogar |18|
| Planificación, reglas y suscripción iCal |15|
| Importación/progreso/IA, trabajos, exportaciones y metadatos por lotes |14|
| Total añadido |60|

## Imagen instalada e integración real de D14 (histórico)

Imagen MCP local probada, sin montar el código:
`sha256:b93c2a7e55e16728d5816cc4f5b8c43df1efa7b378eb639645430209bbdc7045`.
La imagen se construyó después de conectar las 162 herramientas y actualizar las
instrucciones y el skill portable. HTTP y stdio utilizaron el mismo ID inmutable.

Ejecución D14: `artifacts/e2e/mealie-mcp-e2e-76b1ed38a91e/summary.json`.
Resultado: **4/4 casos aprobados**, gate aprobado y `cleanupPassed:true`.

| Recorrido | Positivos nativos | Rechazos SSRF | IA sin configurar | Rechazos de argumentos |
|---|---:|---:|---:|---:|
| stdio · MCP2026-07-28 |159|1|2|162|
| stdio · MCP2025-11-25 |159|1|2|162|
| HTTP Bearer · MCP2026-07-28 |159|1|2|162|
| HTTP Bearer · MCP2025-11-25 |159|1|2|162|
| Total |636|4|8|648|

Se comprobaron 648 recorridos de herramienta y 648 rechazos de argumentos. Las
mutaciones se contrastaron con lecturas independientes de Mealie. Entre las
comprobaciones están persistencia de sustituciones y temporizadores, descarga de
bytes reales, eliminación física de imagen de historial, entradas semanales,
recepción efectiva de acciones en un destino local y resultados parciales de
importación masiva. Los recursos de prueba, volúmenes y red propios se retiraron.

Los dos imports IA verificaron que Mealie no tenía proveedor configurado, el
rechazo esperado, ausencia de nuevas recetas y ausencia de replay. Sus positivos
multipart/SSE están en contratos con respuestas controladas. **No se verificó una
importación satisfactoria contra un proveedor LLM real.** La descarga privada
por archivo se mantiene como rechazo SSRF; su positivo de transporte controlado
no se presenta como descarga pública satisfactoria en esta red desechable.

## Revisión y comprobaciones D14 (histórico)

La revisión independiente de los módulos nuevos, cliente y preservación detectó
dos supuestos de recetarios: PUT/DELETE exigen UUID y el slug lo genera Mealie.
Se añadieron regresiones y se corrigió la resolución del identificador, el nombre
normalizado y la validación de entrada. El repaso posterior no encontró defectos
concretos pendientes en esas correcciones ni en la lectura del hogar.

La integración anterior de 161 herramientas también pasó sus cuatro casos
(`mealie-mcp-e2e-a35d0b2cde86`); la ejecución final de 162 la sustituye como
evidencia del catálogo completo. La primera imagen previa a las correcciones
falló en la mutación de recetarios; se conserva el diagnóstico en artifacts.
Ninguna expectativa histórica fue relajada para aceptar aquel fallo.

Ruff, formato, mypy, workflows, generación documental, wheel/sdist e imagen
runtime se comprobaron dentro del Dev Container. La suite completa y la cobertura
final se registran en los artifacts JUnit/coverage y el inventario de implementación.

Resultado consolidado: **1.794 casos aprobados**, con los cuatro casos `live`
excluidos de la suite ordinaria y ejecutados mediante el controlador E2E. Cobertura:
**96,53 % de líneas** y **87,21 % de ramas**. El gate `--require-all` confirma
162 positivos MCP, 162 rechazos de argumentos y el prefijo histórico intacto.

La primera ejecución final en cuatro shards, simultánea con el E2E, obtuvo dos
timeouts de `initialize` en stdio. Se repitieron los **27 archivos completos** del
shard afectado después de terminar las otras ejecuciones: **529/529 aprobados**,
sin cambiar código, tests, expectativas o tiempos de espera. Los JUnit originales
fallidos se conservan en `artifacts/mealie330/suite-1793726914/`; el JUnit final
combina los tres shards aprobados con esa repetición completa de los mismos casos.
La cobertura combina la medición inicial y la repetición. El informe
`final-summary.json` conserva ambas ejecuciones; `artifacts/pytest.xml`,
`artifacts/coverage.json` y `artifacts/mealie330/compatibility.json` son los
resultados finales utilizados por el gate.

Esta evidencia corresponde a ejecución local amd64. No acredita CI remoto,
validación nativa ARM, publicación GHCR, una release nueva ni despliegue de la
instancia personal del usuario.

## Validación D15 posterior a la revisión

Validación integrada del 2026-11-03 sobre la base Release Please `b674612`
(paquete 0.2.0). Se mantienen 162 herramientas y las 102 definiciones anteriores;
once esquemas nuevos corrigen sus límites anunciados. Las cuatro mejoras de
[D15](../migration/differences.md#d15-correcciones-de-revisión-antes-de-pr) tienen
regresiones persistentes y documentación.

- Suite ordinaria completa: 107 archivos en tres shards, todos aprobados:
  **1.996 casos** en la ejecución inicial. No se solapó el E2E con estos shards.
- La revisión final añadió 14 regresiones al auditor después de iniciar esa
  ejecución. Su ejecución fresca completa, junto al controlador y la limpieza,
  pasó **66 casos**, conservando todos los casos anteriores de esos módulos.
- JUnit consolidado: **2.010 casos únicos aprobados**, cero fallos/errores. Los
  cuatro casos `live` se excluyen de pytest ordinario y se ejecutan con el runner.
- Cobertura del producto: **96,56 % de líneas** y **87,35 % de ramas**. La última
  corrección afecta solo al auditor y sus tests, fuera del código de aplicación
  medido; la fuente del runtime no cambió después de construir la imagen.
- Gate endurecido: **162 positivos MCP y 162 rechazos**, sin fallos, duplicados ni
  atribución a módulos ajenos. Ruff, formato, mypy, linters de workflows,
  documentación generada, enlaces locales, wheel/sdist y tests de imagen pasan.

Los informes originales se conservan en
`artifacts/review-fixes/suite-1793731874/`; `consolidated-summary.json` explica la
combinación con `artifacts/review-fixes/audit-final.xml`. Los resultados finales
son `artifacts/pytest.xml`, `artifacts/coverage.json` y
`artifacts/review-fixes/compatibility.json`. No se descartó ningún fallo para
formar el informe: los tres shards y la ejecución fresca pasaron.

Imagen instalada probada:
`sha256:09cc0487b430ad1984a8991e3cb1c4033839aaa50c7304a39db0c8ac7cec7e24`.
Su revisión OCI es `unknown` deliberadamente, porque contiene el árbol local
todavía sin commit; no se atribuye ese contenido al commit base.

La integración real final
`artifacts/e2e/mealie-mcp-e2e-ff4b241dc1d3/summary.json` pasó **4/4 casos**:
648 recorridos de herramienta, 636 positivos nativos, cuatro rechazos SSRF, ocho
rechazos de configuración IA y 648 rechazos de argumentos. Incluye la prueba
nativa slug/UUID duplicados sin PATCH ni cambios en la receta. El gate del
OpenAPI real pasó antes del bootstrap con credenciales y de las mutaciones;
`cleanupPassed:true` confirma la retirada de los recursos propios.

El OpenAPI de esa ejecución tiene SHA256
`23a7adc37f3ae1921499a43b8d62684a83647235867030a47a0162f608b1560c`;
el [informe API](mealie-3.30-api-audit.json) registra cero diferencias de contrato,
rutas del ámbito sin clasificar o dependencias inexistentes. El contrato
seleccionado conserva 93 operaciones/119 esquemas y procedencia de su captura
original. Sus hashes identifican las capturas; la compatibilidad se comprueba
estructuralmente, sin exigir igualdad de bytes.

La revisión independiente encontró una restricción condicional no detectada
(`dependentRequired`). Se reprodujo su efecto sobre una petición válida y se
cerró mediante una lista explícita de validadores admitidos, con regresiones.
El repaso posterior no encontró defectos importantes pendientes en las cuatro
mejoras. Estos resultados siguen siendo locales amd64: no acreditan CI remoto,
ARM nativo, un LLM real, una publicación ni un despliegue personal.
