# Contribuir

Trabajar en el [Dev Container](docs/development.md). Mantener los contratos del catálogo, añadir pruebas de comportamiento y ejecutar los checks documentados antes de proponer cambios. [Arquitectura](docs/architecture.md) y [compatibilidad](docs/migration/differences.md).

Usar las plantillas de issues para errores reproducibles y propuestas. Leer el
[código de conducta](CODE_OF_CONDUCT.md); comunicar vulnerabilidades mediante
[el canal privado de seguridad](SECURITY.md), sin publicar detalles ni credenciales.

Crear una rama y una PR hacia `main`. El título debe usar un tipo Conventional
Commit admitido en [la guía de CI](docs/ci.md#versiones-y-archivos). Explicar el
problema, el resultado del cambio y las comprobaciones realmente ejecutadas.
No editar versiones manualmente: Release Please gestiona las propuestas de release.

La política de merge exige los checks `Verify amd64`, `Verify arm64`,
`Analyze python` y `Analyze actions`, la rama actualizada y las conversaciones
resueltas. No exige aprobaciones de otra persona para permitir mantenimiento
individual; las contribuciones externas se revisan antes de fusionarlas.
