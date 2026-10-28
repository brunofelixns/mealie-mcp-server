# P23: resultados del escaneo de imagen

Fecha:2026-10-28. Trivy0.76.1 fijado por digest790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c. Base de vulnerabilidades actualizada2026-10-28T07:10:42Z. Se analizan archivos exportados de amd64 y arm64, sin acceso del escáner al socket Docker. Los informes JSON y CycloneDX están en artifacts/P23-{amd64,arm64}-final-scan.*, fuera de Git; CI conserva informes como artefactos cuando se ejecute.

| Resultado | amd64 | arm64 |
|---|---:|---:|
| Componentes CycloneDX |163|163|
| Avisos totales |242|242|
| CRITICAL reportados |2|2|
| HIGH reportados |59|59|
| HIGH/CRITICAL con FixedVersion disponible |0|0|
| Hallazgos de secretos |0|0|
| Avisos en paquetes Python tras retirar pip |0|0|

El primer build produjo250 avisos:242 de Debian y8 de paquetes Python vendorizados en pip de la imagen base. msgpack y urllib3 no estaban en uv.lock; intentar actualizar esas dependencias no modificó el lock. Se verificó su ubicación física en la capa de Python. Se retiraron pip y el bootstrap ensurepip del runtime, que no instala paquetes al ejecutar. Un test primero falló con AssertionError:pip; el nuevo build pasa y elimina esos ocho avisos sin añadir exclusiones al escáner.

Los242 avisos restantes pertenecen al sistema Debian12.15. **No se ha obtenido una imagen sin vulnerabilidades**, ni se interpreta la ausencia de FixedVersion como ausencia de riesgo. No se añadieron .trivyignore, VEX ni filtros que borren hallazgos. El gate CI rechaza secretos y HIGH/CRITICAL corregibles; los avisos restantes requieren revisión antes de un despliegue público y en cada actualización.

Los dos CRITICAL reportados son:

- CVE-2025-7458, libsqlite3-0 3.40.1-2+deb12u2. [Debian](https://security-tracker.debian.org/tracker/CVE-2025-7458) marca bookworm vulnerable, sin DSA por impacto menor, y trixie corregido. La descripción exige poder ejecutar SQL arbitrario. El MCP no ofrece una herramienta SQL ni una base de datos propia y las tareas MCP están desactivadas; esto limita el escenario directo descrito, **sin demostrar que todas las dependencias sean inexplotables**.
- CVE-2023-45853, zlib1g 1:1.2.13.dfsg-1. [Debian](https://security-tracker.debian.org/tracker/CVE-2023-45853) sitúa el fallo en MiniZip, mantiene el source package zlib de bookworm como vulnerable y lo corrige en trixie. No se ha emitido una declaración VEX para excluir el binario de esta imagen; se conserva el hallazgo completo.

Se mantiene la base fijada y ICU72 por la compatibilidad de ordenación ya demostrada. Una actualización de Debian/ICU debe volver a validar ese contrato y las dos arquitecturas; no se presenta como una actualización hecha durante esta tarea. El aislamiento no root, filesystem de solo lectura, ausencia de compiladores/pip y separación de credenciales reduce superficie operativa, pero no corrige esos paquetes del sistema.

Los hashes exactos se registran en [runtime-images.json](runtime-images.json). Los informes son una observación fechada de esas imágenes y esa DB; no garantizan el resultado de un build futuro ni de un dominio/proxy de producción. Ninguna imagen se ha publicado.
