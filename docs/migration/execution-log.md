# Execution ledger — plan: docs/superpowers/plans/2026-10-27-python-migration.md

2026-10-27: usuario autoriza comenzar la implementación. Método: secuencial nativo. P01 activa.

## Preflight

| Productor -> consumidor | Interfaz | Resolución |
|---|---|---|
| P01 -> P02 | Contenedor sin lock -> sync frozen | El primer arranque omite sync hasta crear el lock; se verifica después. |
| P03 -> P06 | Corpus -> adaptador de comparación | Compartir tests/support/contracts.py; no cambiar snapshots para ocultar diferencias. |
| P04 -> P05 -> P06 | Settings/JSON/UNSET -> cliente -> lifespan | Tipos y firmas comunes del plan; cliente y cachés por configuración. |
| P07 -> P09/P10 | Matching -> vocabularios | Sin selección semántica ni creación implícita. |
| P12 -> P13/P14 | Lecturas/batch -> mutaciones/planes | Reutilizar cliente y concurrencia4; escritores5 donde corresponda. |
| P15 -> P16/P17 | Auditoría -> escrituras | Lectura sin efectos; verificación y rollback propios de cada receta. |
| P20 -> P21/P22 -> P23 | Catálogo -> transporte -> imagen | Un registro de78 herramientas y un prompt compartido. |

## Rulings

- P01: trabajar en la carpeta nueva y rama migration/python del upstream fijado, conservando docs; el plan ya define este bootstrap y no existe un checkout principal previo que aislar. No crear otro worktree duplicado.
- Ejecución: usar este ledger versionado y el estado JSON en docs como registro durable. Los helpers de la skill esperan encabezados Task N y el plan aprobado usa P01..P24; no renombrar ni duplicar el plan para depender de ese parser.
- Docker Desktop: acceso al daemon denegado dentro del sandbox; comprobación escalada autorizada y exitosa. Ejecutar Docker con el permiso necesario; no instalar/runtime de aplicación en el host.
- P06: registro mediante Tool/ToolResult públicos de FastMCP4, JSON Schema explícito y modelo Pydantic estricto. jsonschema valida el contrato capturado; no hay dispatcher REST genérico ni outputSchema/structuredContent nuevo. Los mensajes de validación seguros identifican campos en lugar de copiar entradas del cliente.
- P07: añadir PyICU/ICU para reproducir localeCompare en-US observado; trim ECMAScript y longitud UTF-16. Motor callback compartido detrás de la interfaz lookup_candidates del plan, sin variar el contrato MCP.
- P08: resolve_organizer_values devuelve ResolveResult (resolved/created/missing), preservando información del original. El plan abreviaba esa salida a list; actualizarlo evita perder los valores no resueltos que necesitan P13/P14. D06/D07 caracterizadas con el runner original y expectativas separadas.
- P09: modelos transforman solo los campos que el original transforma; validar después contra el esquema preserva trim antes de maxLength. JsonInteger conserva la semántica de números JSON integrales. Comparador/fake distinguen bool de number. Mecánica REST food/unit compartida con handlers MCP explícitos.
- P12: ambos lotes de lectura originales devuelven detalles completos; get_recipes_batch no añade un flag detailed que cambie la proyección. Resolver de filtros ID/name/slug separado del resolver de asignaciones ID/slug/name. Arrays vacíos en create_recipe cuentan como presentes y provocan GET/PUT como en JavaScript.
- P13: mecánica de colecciones compartida en services/recipe_organizers.py; políticas de taxonomía/utensilios y respuestas batch siguen separadas. Locks solo por lote y para entradas createMissing:true; sin cache o permiso global. patch_recipe delega su flujo a un servicio y conserva el caso legacy de flags sin colecciones.
- P14: workflows en services/mealplans.py, REST y handlers separados. Defaults breakfast se incluyen explícitamente al serializar creación/append; replace no los hereda. El harness solo ignora orden entre solicitudes concurrentes declaradas, nunca entre fases; bool/number, cardinalidad y omisión/null se comparan estrictamente.
- Revisión F2 interna: ejecutar-plans exige una revisión fresca de toda la rama al final, no un revisor por tarea. Se reserva la delegación de revisión para P24 y se registra F2 en evidence/F2.md; no se interrumpe la ejecución para pedir confirmación entre fases.

## Evidencia

- Docker Desktop Linux Engine28.3.0, linux/amd64, accesible tras comprobación escalada.
- Historial incorporado mediante alpine/git2.49.1 fijado por digest; HEAD d027e1b4a314d781a322f1f91e37840f01464d77; rama migration/python. docs preservada y upstream solo lectura.

Task P01: complete — apertura real del Dev Container y checks Docker/Python/uid/volúmenes passed; evidencia evidence/P01.md. P02 en curso.

Task P02: complete — RED de wheel instalado observado y GREEN1/1, Ruff/mypy/build y reapertura frozen passed. P03 en curso.
P03: Ruling: Node26 no incluye Corepack ni Yarn; el runner instala Yarn1.22.22 por npm según packageManager upstream, sin cambiar código/lock original. Coste si falla: reproducibilidad del entorno de referencia; se verifica con suite original.

Task P03: complete — catálogo real78/78, prompt/instrucciones y fake en red Docker; suite original1058/1058, suite Python3/3. Evidencia P03.md. P04 en curso.

Task P04: complete — dos ciclos RED/GREEN observados; suite28/28, Ruff/mypy passed. P05 en curso.

Task P05: complete — suite53/53, Ruff/mypy passed; HTTP real contra fake y límites/orden verificados. P06 en curso.

Task P06: complete — suite68/68, Ruff/mypy passed; evidencia evidence/P06.md. P07 en curso.

Task P07: complete — suite94/94, Ruff/mypy passed; evidencia evidence/P07.md. P08 en curso.

Task P08: complete — suite135/135, Ruff/mypy passed; evidencia evidence/P08.md. P09 en curso.

Task P09: complete — suite220/220, Ruff/mypy passed; evidencia evidence/P09.md. P10 en curso.

Task P10: complete — suite247/247, Ruff/mypy passed; evidencia evidence/P10.md. P11 en curso.

Task P11: complete — suite290/290, Ruff/mypy passed; evidencia evidence/P11.md. P12 en curso.

Task P12: complete — suite328/328, Ruff/mypy passed; evidencia evidence/P12.md. P13 en curso.

Task P13: complete — suite403/403, Ruff/mypy passed; evidencia evidence/P13.md. P14 en curso.

Task P14: complete — suite436/436, Ruff/mypy passed; evidencia evidence/P14.md. P15 en curso.

Task P15: complete — suite521/521, Ruff/mypy passed; evidencia evidence/P15.md. P16 en curso.

Task P16: complete — suite568/568, Ruff/mypy passed; evidencia evidence/P16.md. P17 en curso.

Task P17: complete — suite608/608, Ruff/mypy passed; evidencia evidence/P17.md. P18 en curso.

Task P18: complete — suite693/693, Ruff/mypy passed; evidencia evidence/P18.md. P19 en curso.

Task P19: complete — suite787/787, Ruff/mypy passed; evidencia evidence/P19.md. P20 en curso.

Task P20: complete — suite801/801, Ruff/mypy passed; evidencia evidence/P20.md. P21 en curso.

Task P21: complete — suite814/814, Ruff/mypy passed; evidencia evidence/P21.md. P22 en curso.

Ruling: stdio usa un puente POSIX acotado para traducir señales a EOF — el lector AsyncFile del SDK no responde a cancelación — el runtime validado es Linux en contenedor; Windows nativo queda sin validar.

Ruling: configurar el limitador público del manager HTTP después de startup — FastMCP4.1.4 no expone el límite4MiB del SDK2.3.0 y la imagen10MiB es obligatoria — una actualización que cambie la distribución de la ruta falla al arrancar; los tests cubren ambas eras.

Ruling: conservar la salida143 de Uvicorn tras SIGTERM — la señal se reemite después del cleanup — distinguir señal esperada de fallo, verificando también cierre y logs seguros.

Task P22: complete — suite831/831, Ruff/mypy passed; evidencia evidence/P22.md. P23 en curso.

Ruling: retirar pip/ensurepip del runtime en lugar de añadir dependencias no usadas — los ocho avisos Python estaban vendorizados en la base, no en uv.lock — la imagen no admite instalar paquetes al ejecutarse; se reconstruye desde el lock.

Ruling: conservar el informe completo Debian12 y permitir solo cero secretos/cero HIGH-CRITICAL corregibles en el gate — no hay FixedVersion para los242 avisos del OS en este canal — los dos CRITICAL y59 HIGH siguen documentados y requieren revisión antes de exposición pública; no se declara imagen sin vulnerabilidades.

Ruling: Compose de producción con secrets de archivo se lanza desde el host del daemon — sus bind mounts no resuelven paths internos /workspaces del Dev Container — no requiere Python en el host; los tests desde el Dev Container utilizan copias API y redes Docker.

Task P23: complete — suite841/841, Ruff/mypy passed; evidencia evidence/P23.md. P24 en curso.

P24: suite929/929,3 deseleccionados, cobertura95,982974% líneas/87,472284% ramas; checker sobre JUnit real confirma78 positivos+78 rechazos. Integración Mealie3.29.0 desechable pasa directa y por Compose; retiro TS y documentación implementados. Build final/revisión aún pendientes.

Ruling: reducir el drenaje Uvicorn a3s —40+35 de recuperación+5 de pool superaban stop_grace_period45 — requests largas reciben cancelación durante parada; las mutaciones emitidas conservan su limpieza protegida de35s y el presupuesto total es43s.

Ruling: registrar la conformidad externa como limitada, sin quitar Bearer — el runner npm0.1.16 no admite cabeceras y server-initialize recibe401; tampoco ofrece2026-07-28 — no se afirma certificación externa ni compatibilidad universal; SDK oficial/FastMCP de ambas eras tienen pruebas propias.
