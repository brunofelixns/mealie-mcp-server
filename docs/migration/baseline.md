# Baseline de compatibilidad

[P03 verificada](evidence/P03.md): commit original fijado,1058pruebas originales pasan y catálogo real78/78 capturado.

Dentro del Dev Container:

```bash
docker build -f tests/reference/Dockerfile -t mealie-mcp-reference:upstream-d027e1b .
uv run python scripts/run_reference_checks.py
uv run python scripts/capture_reference.py --output /tmp/reference-capture
uv run pytest tests/contracts/test_reference_catalog.py -q
```

No sobrescribir snapshots para resolver una diferencia del port. Capturar en otra ruta, comparar y registrar el motivo. Todos los escenarios usan fixtures y una API key explícitamente falsa. El fake vive en el Dev Container y los runners se unen a su red Compose; no se montan rutas Linux internas como paths del daemon Windows.

La captura guarda su propio testsExecuted=false porque ese comando no ejecuta la suite. La suite se verifica por separado con el informe del runner; el inventario enlaza ambas evidencias.
