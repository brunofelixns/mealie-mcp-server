# Trabajo en este repositorio

Desarrollar y ejecutar Python, tests y builds en el Dev Container Linux. El host se utiliza como editor y launcher Docker; no instalar runtimes de aplicación en él.

El contrato público reside en src/mealie_mcp_server/resources/tool-catalog.json y se confronta con las capturas inmutables de tests/fixtures/compatibility. Registrar handlers explícitos por familia, modelos Pydantic estrictos con aliases originales y acceso al cliente mediante lifespan. Mantener los servicios independientes de MCP y conservar campos Mealie desconocidos en los payloads que lo requieran.

No modificar una expectativa de baseline para ocultar una regresión. Documentar diferencias intencionadas en docs/migration/differences.md. Conservar omisión/null/0/false/[], orden, errores, límites y efectos secundarios. Ningún retry automático de escrituras.

Añadir pruebas de comportamiento para cambios funcionales; usar los checks de docs/development.md. Regenerar documentación con scripts/generate_docs.py y comprobar scripts/check_compatibility.py. stdout pertenece a JSON-RPC en stdio; no registrar credenciales, cuerpos de recetas o URLs firmadas.

La auditoría Node opcional solo sirve para reproducir la referencia upstream. No introducir Node/TypeScript en el producto, su instalación ni el CI ordinario. Publicar imágenes, paquetes, commits remotos o endpoints requiere un destino y autorización correspondientes; los builds locales no publican.
