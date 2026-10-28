# Limpieza posterior a la migración

Solicitada por el usuario después del cierre P24: retirar restos de TypeScript y conservar lo necesario para desarrollar, verificar y operar la aplicación Python.

## Elementos retirados

- Carpetas vacías .husky, src/__tests__, src/api, src/lib y src/tools.
- .env.template redundante; .env.example es la plantilla vigente.
- Reglas Node/Yarn/npm obsoletas de .gitignore y .dockerignore. Este último excluye además cobertura Python local.
- tests/reference y sus tres archivos, incluido el último JavaScript.
- Scripts temporales capture_reference.py, capture_cases.py, capture_last_made.py y run_reference_checks.py.
- Las dos pruebas de test_reference_catalog.py que iniciaban el servidor Node y su marcador reference; las pruebas de catálogo y contrato Python permanecen.
- Logo upstream sin referencias activas en la documentación o aplicación.
- Scripts auxiliares y logs locales de .superpowers creados solo para ejecutar las fases de migración; las evidencias durables permanecen en docs/migration y artifacts.

Las capturas JSON/texto originales, su licencia, el inventario y las pruebas de compatibilidad son necesarios para demostrar la paridad y se conservan. El código Python, sus dependencias de producción, Dev Container, CI, Dockerfile y Compose permanecen operativos. Los antiguos runners se pueden consultar en el commit17173ce73092290af7a6af42a7bbac2596e589d1 del historial Git.

Los registros P01..P24 y el plan son históricos: sus comandos y rutas identifican lo ejecutado durante la migración. Las instrucciones vigentes están en [desarrollo](../development.md) y [baseline](baseline.md).

## Verificación

Checks ejecutados dentro del Dev Container después de retirar los archivos:

- `uv sync --frozen --group dev`: instalación correcta sin modificar uv.lock.
- Ruff y formato: correctos; mypy estricto:82 fuentes sin errores.
- Suite completa: **929 tests pasan,1 deseleccionado (integración live),420,64s**. Los dos tests que iniciaban Node ya no se distribuyen; todas las regresiones Python permanecen.
- Checker sobre el JUnit actual: **78 positivos+78 rechazos**,246 capturas preservadas. Cobertura95,982974% líneas y87,472284% ramas, superior a90/85.
- Documentación generada --check y enlaces Markdown locales: correctos; no quedan instrucciones activas que invoquen los archivos retirados.
- `uv build`: wheel y sdist2.1.0 correctos. Ambas configuraciones Compose validan y release_gate confirma24 tareas verificadas.
- Sin archivos propios JS/TS en el checkout versionado; sin cambios en src, fixtures originales, uv.lock, Dockerfile, CI o Compose. No hace falta reconstruir las imágenes por una retirada de herramientas de desarrollo y documentación.

Se retiraron10 archivos versionados,26 auxiliares locales y8 carpetas. Los dos logs de reapertura/rebuild con referencias históricas se conservaron mediante copia verificada por SHA-256 en artifacts/migration-P02-devcontainer-reopen.log y artifacts/migration-P09-devcontainer-rebuild.log.

Artefactos locales: artifacts/cleanup-suite.log, cleanup-pytest.xml, cleanup-coverage.json, cleanup-compatibility.json, cleanup-structure.json y cleanup-build.log. Las imágenes finales verificadas en P24 y sus límites de seguridad siguen descritos en [aceptación](acceptance.md).
