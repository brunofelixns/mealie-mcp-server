# Pruebas locales E2E de todas las herramientas MCP

> Ejecución autorizada por el usuario: secuencial, con superpowers:executing-plans y pruebas de comportamiento antes de implementar. No requiere nuevas preguntas para continuar.

**Objetivo:** invocar las78 herramientas contra Mealie real desde la imagen de producción MCP, por stdio y HTTP con Bearer, con datos locales desechables y evidencia verificable.

**Diseño:** Compose crea Mealie3.29.0 fijado por digest, un servidor HTTP de imágenes estáticas y el MCP HTTP en una red interna sin puertos publicados. El Dev Container actúa como controlador de tests y se une temporalmente a esa red; lanza el MCP stdio como otro contenedor de la misma imagen. Bootstrap genera credenciales de la instancia desechable y un Bearer independiente. Ningún servicio de aplicación recibe el socket Docker o mounts de código.

**Tecnologías:** Python3.14, Docker Compose, pytest/pytest-asyncio, SDK MCP oficial2.3.0, httpx2. Sin dependencias de producto nuevas ni Node.

## Restricciones y decisiones

- Mealie: ghcr.io/mealie-recipes/mealie:v3.29.0@sha256:78eb28b8776d0bad40c5e605c72b3f4f5976793e491558c7dcbdfc04c835d4bc.
- Misma imagen instalada para MCP HTTP y stdio; registrar image ID, versión y plataforma. Sin importar create_server en el recorrido E2E.
- Cuatro recorridos: stdio/HTTP × MCP2026-07-28/2025-11-25. Cada uno invoca las78 herramientas y comprueba78 rechazos de argumentos desconocidos.
- Matiz explícito: set_recipe_image_from_file rechaza las direcciones privadas por diseño. Su recorrido totalmente local verifica el rechazo SSRF y que la imagen no cambie. Su descarga positiva desde una URL pública no queda cubierta por E2E local; no se desactiva esa protección ni se presenta como éxito CRUD.
- Las otras77 herramientas deben completar una operación positiva con verificaciones de contenido/estado; no admitir errores del proveedor como éxitos genéricos.
- Bootstrap y fixtures solo pueden escribir en contenedores con etiquetas del proyecto efímero creado por el controlador; nunca aceptar una URL o API key personales como destino.
- Red internal:true, volúmenes con nombre propio por ejecución, sin puertos públicos. Las descargas de imágenes/dependencias ocurren al preparar el entorno; el recorrido de datos no necesita Internet.
- Conservar todas las regresiones Python existentes y los contratos públicos. Corregir defectos descubiertos únicamente con evidencia y tests; documentar diferencias de compatibilidad si fueran necesarias.
- Capturar informes incluso si falla una fase y eliminar únicamente los contenedores/volúmenes propios; desconectar el controlador de la red al finalizar. Nunca usar prune.
- Credenciales en archivos temporales/volumen, excluidas de informes y logs. El reporte enumera herramientas, comprobaciones y resultados, sin copiar tokens.
- Mantener la rama de trabajo migration/python y el Dev Container existentes, conforme al contexto autorizado. No crear otro checkout ni publicar una imagen.

## Interfaces y archivos

| Archivo | Responsabilidad |
|---|---|
| compose.integration.yaml | Servicios Mealie/assets/MCP y red/volúmenes desechables |
| tests/e2e/runner.py | Ciclo de vida, build, bootstrap, pytest, artefactos y limpieza |
| tests/e2e/stack.py | Operaciones Docker y verificación de propiedad/aislamiento |
| tests/e2e/context.py | Lectura segura de credenciales y conexiones a servicios propios |
| tests/e2e/scenarios.py | Fixtures y llamadas a las78 herramientas con comprobaciones reales |
| tests/e2e/evidence.py | Registro y gate de cobertura por transporte/era |
| tests/integration/test_mealie_roundtrip.py | Cuatro recorridos reales por clientes SDK oficiales |
| tests/unit/test_e2e_evidence.py | Rechazar informes incompletos, errores inesperados o secretos |
| tests/unit/test_e2e_cleanup.py | Intentar toda la limpieza aunque falle una fase anterior |
| tests/unit/test_shopping_api.py | Regresiones de las correcciones D10/D11 descubiertas con Mealie real |
| docs/testing/local-e2e.md | Operación, matriz y límites de la suite |
| docs/testing/local-e2e-progress.md | Ledger de ejecución y decisiones |
| .github/workflows/ci.yaml | Ejecutar controlador y retener artefactos E2E |

## Tareas

- [x] **1. Evidencia antes de implementación.** Escribir tests del gate que fallen por ausencia del módulo: faltan herramientas/eras, duplicados, error inesperado, falta de comprobaciones y posible fuga de secreto. Implementar evidencia con resultados diferenciados, hacer pasar y registrar RED/GREEN.
- [x] **2. Stack y bootstrap.** Sustituir el runner en memoria por servicios reales; verificar imagen/versiones, credenciales separadas, red interna, ausencia de puertos/mounts de código y cleanup en fallo. Usar nombres únicos por ejecución. Guardar logs sin secretos.
- [x] **3. Catálogo completo.** Implementar escenarios deterministas por dominio, preparar y borrar IDs propios, validar también persistencia con lecturas directas Mealie. Ejecutar los cuatro recorridos y resolver cada fallo sin rebajar aserciones para ocultar problemas. Gate exacto78/78 y78 rechazos por recorrido.
- [x] **4. Integración y cierre.** Actualizar CI y docs; ejecutar Ruff/formato/mypy, tests de evidencia, suite ordinaria y E2E. Revisión independiente de este cambio y única pasada de fixes importantes. Registrar comandos/medidas/límites, hacer commit y subir a la rama autorizada.

## Focos de revisión

1. Una variable heredada o un alias DNS no debe redirigir escrituras a un Mealie ajeno.
2. Repetición/fallo parcial: informes incompletos deben fallar y cleanup no puede borrar recursos de otra ejecución.
3. Igualdad real de imagen HTTP/stdio y ausencia de cliente MCP en memoria o mocks de la API Mealie.
4. El rechazo privado del archivo no debe ocultar otro error ni aparecer como descarga positiva.
5. Credenciales y metadatos: no incluir tokens en pytest repr, argumentos Docker, artifacts o Git; Bearer MCP separado de la credencial Mealie.

## Comprobaciones previstas

```sh
uv run pytest tests/unit/test_e2e_evidence.py -q
uv run python -m tests.e2e.runner
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python scripts/generate_docs.py --check
uv run pytest -q
```
