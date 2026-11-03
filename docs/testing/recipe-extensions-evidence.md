# Evidencia local de las operaciones adicionales de recetas

Fecha: 2026-11-03. Rama local `codex/complete-recipe-tools`, checkout con cambios
sin publicar sobre `274785f437e0ad26035d855db8d056537493d109`.

## Mealie real desechable

Comando ejecutado en el Dev Container Linux:

```bash
uv run --frozen python -m tests.e2e.runner
```

Resultado: **4 passed**, Mealie **3.29.0**, imagen runtime instalada `amd64`,
red interna sin puertos publicados ni credenciales personales. La limpieza de
contenedores, red y volúmenes de esta ejecución terminó correctamente.

| Transporte / protocolo | Herramientas verificadas | Positivos | Rechazo SSRF esperado | Rechazos de argumentos |
|---|---:|---:|---:|---:|
| stdio / 2026-07-28 | 102 | 101 | 1 | 102 |
| stdio / 2025-11-25 | 102 | 101 | 1 | 102 |
| HTTP / 2026-07-28 | 102 | 101 | 1 | 102 |
| HTTP / 2025-11-25 | 102 | 101 | 1 | 102 |
| Total | 408 | 404 | 4 | 408 |

Las 24 adiciones tienen operaciones positivas en los cuatro recorridos. Se
contrasta persistencia mediante lecturas independientes, incluidos CRUD de
notas/comentarios/historial/tokens, metadatos, adjuntos y el roundtrip JSON/ZIP.
La excepción es la herramienta histórica de descarga por archivo, que mantiene
el rechazo SSRF esperado en una red privada: no se desactiva su protección.

Manifiesto local: `artifacts/e2e/mealie-mcp-e2e-4678f5540d03/summary.json`.
Runtime exacto: `sha256:867555eec818f738b39b87d8ddf6c235757324eda39b8967ebf94bd7059cd8cf`.
Es evidencia local `amd64`; no demuestra validación ARM, CI alojada ni publicación.

## Compatibilidad y empaquetado

Los fixtures históricos de `tests/fixtures/compatibility` no se modifican. El
catálogo conserva exactamente las 78 definiciones originales y añade 24 nuevas.
Ruff, formato, mypy, checks de workflows, documentación generada, wheel/sdist y
build local de runtime se comprobaron durante la implementación. La evidencia
JUnit y de cobertura de la suite ordinaria se guarda en `artifacts/pytest.xml`,
`artifacts/coverage.json` y `artifacts/coverage.xml`.

La ejecución completa registró **1.380 passed, 3 failed, 4 deselected** en
1.263,45 s. Los tres fallos correspondían a expectativas antiguas de catálogo:
una buscaba las herramientas nuevas en el baseline de 78; dos esperaban los
recuentos E2E 78/77/312. Se corrigieron sin cambiar capturas originales y se
reejecutaron sus casos y rechazos relacionados: **11 passed** en 16,62 s,
registrados en `artifacts/recipe-extensions/recheck.xml`. No se repitió la suite
completa después de estos cambios exclusivamente en pruebas; se conservan los
dos informes para mostrar con precisión la validación realizada.

Tras la revalidación, `check_compatibility.py --require-all --coverage-json
artifacts/coverage.json --junit-xml artifacts/pytest.xml` confirmó **102 positivos
y 102 rechazos ejecutados**, baseline de 78 intacto y 24 adiciones. Cobertura:
**96,10 % de líneas y 87,06 % de ramas** (mínimos: 90 % y 85 %). El informe
estructurado está en `artifacts/recipe-extensions/compatibility.json`.
