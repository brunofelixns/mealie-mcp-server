# Baseline de compatibilidad

[P03 verificada](evidence/P03.md): commit original fijado,1058pruebas originales pasan y catálogo real78/78 capturado.

Las capturas originales de tests/fixtures/compatibility son datos inmutables que siguen utilizándose en las pruebas Python. Su procedencia, commit upstream y manifest se conservan. No hace falta Node para comprobar la compatibilidad actual:

```bash
uv run pytest tests/contracts -q
uv run python scripts/check_compatibility.py --require-all
```

El runner Node, sus scripts de captura y dos pruebas que dependían de ejecutarlo fueron herramientas temporales de migración. Se retiraron en la [limpieza final](cleanup.md), conservando el corpus y todas las regresiones Python. Para investigar o reproducir la auditoría histórica, consultar esos archivos en el commit local17173ce73092290af7a6af42a7bbac2596e589d1, en un checkout separado; no son instrucciones del entorno actual.

No sobrescribir snapshots para resolver una diferencia del port. Si se revisa upstream de nuevo, capturar en otra ruta, comparar y registrar el motivo. Todos los escenarios usan fixtures y una API key explícitamente falsa.

El manifest histórico guarda testsExecuted=false porque la captura no ejecutaba la suite original. Su ejecución se verificó por separado en P03; el inventario enlaza ambas evidencias. El checker sin JUnit valida el índice declarativo; la evidencia de ejecución procede de pytest y sus reportes.
