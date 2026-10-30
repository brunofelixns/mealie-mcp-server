# Simplificar el despliegue Docker

El usuario pide un Compose más sencillo. Se divide la carpeta de despliegue por transporte: HTTP en `docker/compose.yaml`, stdio en `docker/compose.stdio.yaml`, sin anchors ni perfiles. HTTP carga `.env`; la plantilla muestra cuatro valores a completar y dos opcionales. stdio conserva una lista explícita de variables, sin transmitir el Bearer HTTP. Se conservan raíz de solo lectura, usuario sin privilegios de la imagen, tmpfs, capabilities, no-new-privileges, límite de procesos, parada y sonda HTTP.

La variante raíz `compose.production.yaml`, con builds y secretos de archivo, conserva su interfaz. Se actualizan comandos y configuración de clientes en README y docs. El cambio de comando stdio y la carga HTTP con `env_file` se explican en `docker/README.md`.

Antes de editar se verificó por lectura que GHCR ya ofrece la etiqueta0.1.0 con digest `sha256:9b76115fa5b4796408c779c30f4ff96ceea63ba4db3b8dff716bfa43576b571b`. Su índice referencia los runtimes y las attestations de ambas arquitecturas del run `cf036c87d382`. La recuperación de publicación anterior ya no está pendiente; esta tarea no sube ni modifica imágenes.

Verificación: RED del nuevo caso por ausencia del archivo stdio; GREEN con los archivos separados. Las pruebas copian el bundle a una carpeta temporal, crean su propio `.env`, resuelven ambos Compose y ejecutan HTTP/Bearer y stdio con el mismo runtime publicado, sin credenciales personales. Comprobar también en ARM emulado, Ruff, formato, documentos generados y checker de compatibilidad. No es necesario reconstruir la imagen: no hay cambios en la aplicación.

Resultados:

- El archivo HTTP pasa de 57 a 32 líneas; `.env.example` muestra solo cuatro valores a completar y dos opcionales. Se mantiene la configuración de protección y se hereda el UID10001 de la imagen. stdio usa su propio nombre de proyecto predeterminado.
- amd64: 3/3 pruebas de despliegue inicialmente en29,74s y repetición final con el helper actualizado en26,84s.
- La primera ejecución QEMU agotó los tiempos anteriores. Un diagnóstico secuencial midió `/readyz` a los 58,82s con el Compose anterior y 85,16s con el simplificado. Se ajustan solo los presupuestos de las pruebas emuladas: arranque120s y RPC90s. Los márgenes nativos siguen en60s/40s; la configuración de producción conserva sus valores. El helper Docker mantiene75s por defecto y permite un timeout mayor únicamente donde se solicita.
- arm64 emulado tras ajustar el margen: 3/3 pruebas, 185,39s. No se presenta como validación en hardware ARM nativo.
- Documentación generada: 4/4 casos. Ruff/formato y mypy correctos. El checker sobre la evidencia completa `cf036c87d382` confirma78/78,246 casos y cobertura95,99%/87,50%; no es una ejecución nueva de esa suite completa.
- Se actualizan la guía de publicación con PAT classic y la evidencia observada de `0.1.0`, para distinguir el login web de una autorización real de GHCR y el cliente Docker del Dev Container del cliente del servidor de despliegue.

La última lectura de GitHub confirma que el paquete sigue privado y asociado a `brunofelixns/mealie-mcp-server`; un servidor nuevo necesita login de lectura en su propio cliente Docker. No se consulta la configuración personal `.env` ni se cambian sus valores.

Migración de comandos: en `docker/`, sustituir `--profile stdio` por `-f compose.stdio.yaml`. HTTP lee `.env` junto al YAML; `--env-file` por sí solo solo cambia la interpolación, por lo que otro archivo HTTP requiere ajustar `env_file`. El archivo raíz con secretos y builds conserva sus perfiles.
