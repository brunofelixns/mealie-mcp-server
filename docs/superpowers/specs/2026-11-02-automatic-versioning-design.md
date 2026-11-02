# Versionado automático en CI

El usuario solicita que la subida de versión también sea automática, como parte
del CI que ya prueba y publica GHCR. Se conserva Python en el Dev Container y el
contrato público de las 78 herramientas.

## Enfoque

Se utiliza Python estándar para preparar una versión semántica desde los commits:
`!` o un footer `BREAKING CHANGE:` / `BREAKING-CHANGE:` incrementan major;
`feat` y `fix` incrementan minor; cualquier otro cambio incrementa patch. Prevalece
el cambio de mayor impacto de todo el lote. La regla sigue las convenciones de
este repositorio, incluida la subida minor para fixes. Se descartaron herramientas
que necesitan Node y un gestor de releases adicional con su propia convención.

`pyproject.toml` es la versión canónica. Un ancla en `.release.json` delimita los
commits nuevos desde la última publicación Python verificada. No se toma el mayor
tag histórico: los tags v1/v2 heredados pertenecen al producto anterior.

## Flujo

Un job sin escritura prepara pyproject, el paquete propio del lock, la etiqueta
Docker y ambos catálogos README, y crea un commit local reproducible y un bundle.
Ambos runners nativos restauran ese commit y prueban/construyen su contenido.
Las PR y ramas distintas de main conservan su versión y carecen de publicación.

Solo tras pasar ambos runners, el publicador restaura el mismo commit, comprueba
que main no avanzó, sube las imágenes probadas con tag de SHA, y envía main y el
tag vX.Y.Z de forma atómica, sin force. Publica X.Y.Z y latest con el mismo digest,
y una GitHub Release con notas del lote. El token temporal evita un bucle de CI.

## Fallos y límites

Un fallo de tests no escribe versiones remotas. Una carrera con otro push impide
sobrescribir main. Los tags Git/versionados nunca se reasignan a otro contenido.
Una repetición de jobs fallidos utiliza el mismo bundle, versión y commit; no
incrementa otra vez. Una publicación parcialmente completada se recupera repitiendo
el job con sus artefactos, conservados un día. Git y GHCR no ofrecen una transacción
común: puede existir un tag de Git antes de completarse GHCR, pero el fallo queda
visible y latest no se promociona antes de verificar la versión publicada.

No se añade publicación local, PAT permanente, Node ni cambios en las capturas
inmutables. La implementación y verificación se realizan en la sesión actual.
