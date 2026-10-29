# q_Inv: revisión de diseño y funcionalidad

Fecha: 28 de octubre de 2026. Código revisado: `a8d28ce` (base funcional v0.3.1).

## Resultado

La base funcional probada es estable: pasaron 31 pruebas de backend y el recorrido
automatizado existente de navegador. Las comprobaciones adicionales completaron
alta manual, ajustes, importación XLSX y recuperación visible ante un fallo de API.
No se encontraron bloqueos en los recorridos ejecutados. Esto no certifica toda la
aplicación ni las conexiones con equipos reales.

Hay ocho hallazgos de accesibilidad y uso, además de dos propuestas derivadas de
las preferencias visuales nuevas: dos P1, siete P2 y un P3 en total. Antes del
rediseño conviene resolver contraste y nombres accesibles de diálogos. Después,
mejorar continuidad de teclado y claridad de estados.

No se modificaron HTML, CSS, JavaScript ni lógica de la aplicación. La revisión
usó instancias temporales, datos ficticios y Chrome headless local. No se accedió al
servidor desplegado ni a su base de datos. No se realizó la revisión de código y
seguridad del tercer punto propuesto.

## Preferencias recogidas

El usuario indicó «Braum o Nothing Phone» y tema claro/oscuro con selector.
Se interpreta provisionalmente «Braum» como **Braun**; confirmar esa interpretación
antes de diseñar una nueva identidad.

Dirección propuesta, todavía sin implementar:

- Braun: jerarquía clara, controles comprensibles, alineación precisa y economía de
  elementos. Su enfoque funcional se describe en la
  [historia oficial de diseño](https://secure-us.braun.com/en-us/design/design-and-innovation).
- Nothing: explorar una base monocromática, módulos definidos y detalles técnicos
  contenidos; la referencia de producto es [Phone (2)](https://in.nothing.tech/pages/phone-2).
  Esta traducción a una app de infraestructura es una propuesta propia, no una
  especificación de esas marcas.
- Tipografía convencional legible para tablas, formularios y errores. Si se usan
  detalles de matriz de puntos, reservarlos para identidad o acentos, sin afectar
  la lectura de métricas.
- Reservar rojo, ámbar y verde para significado operativo, acompañado siempre por
  texto o símbolos. El esquema monocromático no debe ocultar alertas.
- Mantener la información funcional de las tarjetas de servidores solicitadas
  originalmente; cambiar su presentación no exige eliminar esas métricas.

## Evidencia y límites

Herramientas: Impeccable audit (detector de fuentes y lista técnica), inspección
visual de capturas, Playwright/Chrome, árbol de accesibilidad de Chrome y pruebas
Python existentes. Se revisaron dashboard, inventario y organización a anchuras
de 1440, 768 y 390 CSS px; además formularios, importación y configuración.
Es emulación de viewport, no una prueba en un teléfono físico.

Los artefactos locales están en `validation/review-2026-10-28/`, ignorada por Git:

- `backend.log`, `browser-smoke.log`: resultados de pruebas.
- `browser-evidence.json`, `supplemental-evidence.json`: medidas y recorridos.
- `detector.json`: resultados automáticos sin filtrar.
- `probe-browser.cjs`, `probe-supplemental.cjs`: recorridos adicionales ejecutados.
- Capturas `dashboard-*`, `inventory-*`, `organization-*`, `manual-form-*`,
  `import-preview.png`, `settings.png`, `dashboard-no-results.png`.

Las capturas y esos datos no se distribuyen con este documento al clonar el repo.
Los scripts de evidencia registran las rutas locales de esta sesión; no son una
nueva suite portable de pruebas de producto.

### Matriz funcional

| Recorrido | Resultado observado | Alcance |
|---|---|---|
| Acceso y cierre de sesión | Correcto en pruebas existentes | Cuentas ficticias locales |
| Alta manual | Registro creado y visible | Sin SSH real |
| Dos campos de IP | Se sincronizan; guardar conserva el último valor editado | Verificado en navegador |
| Edición y asignaciones múltiples | Correcto | Catálogos, ambiente, responsable y etiquetas |
| Organización masiva | Previsualización y confirmación correctas | Incluye selección fuera del filtro |
| Eliminación masiva | Cancelación conserva datos; confirmación elimina los seleccionados | Solo registros ficticios |
| Importación RVTools | Previsualización y alta correctas | XLSX sintético con hoja vInfo |
| Reimportación y errores de importación | Correcto en pruebas de API | UUID, duplicados, unidades y datos inválidos |
| Configuración | Guardado comprobado: 10 minutos / 90 días | Solo base temporal |
| Métricas y estados | Representación de cero, error y falta de configuración correcta | Métricas sembradas; recolector probado con mocks |
| Inventario con 500 registros | 500 filas renderizadas; búsqueda específica devuelve una | Respuesta API sintética, no carga de servidor |
| Error de dashboard | Mensaje visible; se conservan tarjetas previas | Error 503 simulado; ver F03 |
| Consola del navegador | Sin errores JavaScript en recorridos adicionales | No cubre todas las interacciones posibles |

En este Mac, sustituir la respuesta del inventario por 500 registros, renderizar y
abrir la sección tardó aproximadamente 137 ms. Es una observación de una ejecución,
no un benchmark ni una garantía de rendimiento con 500 conexiones SSH.

No se probaron conexiones reales a RHEL, AIX, SunOS o Windows ni un archivo real de
RVTools. Las pruebas de descubrimiento usan salidas y clientes simulados; el
monitoreo periódico actual se anuncia para Linux. La compatibilidad operativa con
cada versión de sistema requiere una matriz posterior con equipos autorizados.

## Auditoría técnica de interfaz

Valoración orientativa sobre la evidencia disponible; no es certificación WCAG.

| Dimensión | Puntos / 4 | Evidencia principal |
|---|---|---|
| Accesibilidad | 2 | Etiquetas y avisos existentes, pero contraste y diálogos con carencias |
| Rendimiento de interfaz | 3 | Dashboard pagina a 12 tarjetas; 500 filas y filtro funcionan en el ensayo local |
| Temas | 1 | Dos tokens globales principales; colores extendidos y sin selector de tema |
| Adaptación | 2 | Sin desbordamiento del documento en los tamaños revisados; tabla y formulario exigen mucho desplazamiento |
| Coherencia de implementación | 2 | Navegación estable; componentes de monitoreo y administración usan tratamientos distintos |
| **Total** | **10 / 20** | **Mejoras significativas de interfaz, con recorridos funcionales operativos** |

El detector emitió 72 señales: 11 de contraste, 17 de texto diminuto, 33 de tamaños
de interfaz reducidos y 11 de preferencias estilísticas. Son señales repetidas,
no 72 fallos independientes. Las alertas sobre Inter, rótulos sobre títulos,
sombras y bordes no se consideran por sí mismas errores: Inter figura como fallback
y no se descarga como fuente externa. La mezcla visual de tarjetas se evalúa como
decisión de diseño, no como una avería.

### P1: resolver primero

**U01 — Contraste insuficiente de textos secundarios.**

- Ubicación: `static/style.css:1`, `.muted`, `.eyebrow`, encabezados y notas de tabla.
- Evidencia: el navegador devuelve texto `rgb(116,130,140)` sobre fondo
  `rgb(245,247,249)`, a 14 px; la relación calculada es aproximadamente 3,7:1.
  El detector también señala combinaciones sobre blanco por debajo de 4,5:1.
- Impacto: lectura difícil de explicaciones y datos secundarios, especialmente en
  pantallas con poco contraste o usuarios con baja visión.
- Recomendación: definir tokens de texto principal/secundario por tema y verificar
  al menos 4,5:1 para texto normal; contrastar también estados y controles.
- Siguiente trabajo sugerido: `$impeccable audit` y `$impeccable harden` sobre los
  componentes corregidos.

**U02 — Los diálogos carecen de nombre accesible explícito.**

- Ubicación: `static/index.html`, `server-dialog`, `catalog-dialog`, `bulk-dialog`
  y `delete-dialog`.
- Evidencia: falta `aria-labelledby`/`aria-label` en los cuatro elementos; al abrir
  el alta manual, el árbol de accesibilidad de Chrome devuelve rol `dialog` y
  nombre vacío. La presencia visual de un h2 no lo asocia automáticamente al diálogo.
- Impacto: la tecnología de asistencia pierde el contexto al entrar al modal.
- Recomendación: asociar cada diálogo a su encabezado y, cuando aporte contexto,
  a una descripción; verificar foco inicial, Escape y retorno de foco.
- Siguiente trabajo sugerido: `$impeccable harden`.

### P2: claridad y continuidad de uso

**U03 — Metadatos y controles usan tamaños de texto muy pequeños.**

- Ubicación: `static/style.css`, encabezados de tabla a 9 px, notas a 10–11 px y
  controles de widgets a 11 px.
- Evidencia: fuentes CSS, detector y capturas desktop/móvil. Botones «Configurar»
  miden aproximadamente 21 px de alto; checkboxes nativos, 13 × 13 px.
- Impacto: baja legibilidad y comodidad táctil.
- Recomendación: escala tipográfica coherente, texto operativo mayor y superficies
  clicables generosas. Un control menor de 24 px no prueba por sí solo incumplir
  WCAG: deben comprobarse sus excepciones de separación y controles equivalentes.
- Siguiente trabajo sugerido: `$impeccable typeset` y `$impeccable adapt`.

**U04 — En móvil, el inventario necesita desplazamientos poco evidentes.**

- Ubicación: `static/index.html`, navegación y tabla; `static/style.css`,
  `.table-scroll` y reglas móviles.
- Evidencia: a 390 px no hay overflow de todo el documento, pero solo se ve una
  parte de las columnas y de la navegación horizontal. La acción Editar permanece
  fija a la derecha, lo cual ayuda.
- Impacto: comparar recursos y localizar secciones requiere descubrir el scroll.
- Recomendación: conservar vista densa de escritorio; en móvil dar prioridad a
  nombre, IP y estado, con expansión de detalle e indicación clara de navegación.
- Siguiente trabajo sugerido: `$impeccable adapt`.

**U05 — La conexión SSH domina el primer tramo del alta manual.**

- Ubicación: `static/index.html`, `server-dialog` y `discovery-panel` abierto.
- Evidencia: en 390 × 844 px el primer viewport del diálogo se dedica a conexión,
  antes de mostrar el nombre obligatorio y la acción de guardar.
- Impacto: el usuario que solo quiere registrar un equipo puede interpretar que
  conectarse por SSH es obligatorio. Guardar manualmente sí funciona.
- Recomendación: distinguir con claridad «Registrar manualmente» y «Descubrir por
  SSH», compartiendo los datos y sin perder lo que ya se haya escrito.
- Siguiente trabajo sugerido: `$impeccable clarify` y `$impeccable layout`.

**F01 — Mensaje incorrecto al filtrar el dashboard sin coincidencias.**

- Ubicación: `static/app.js:104` y `dashboard-empty` en `static/index.html`.
- Reproducción: con tres servidores registrados, buscar `no-existing-server-qa`.
- Resultado: «Agrega servidores y configura sus credenciales SSH…».
- Impacto: confunde ausencia de resultados con ausencia de inventario.
- Recomendación: separar inventario vacío y filtros sin coincidencias; ofrecer
  limpiar búsqueda y filtros. El inventario tabular ya diferencia este caso.
- Siguiente trabajo sugerido: `$impeccable clarify`.

**F02 — La actualización de tarjetas hace perder el foco del teclado.**

- Ubicación: `static/app.js:108`, `replaceChildren`, y actualización cada 20 s
  en `static/app.js:114`.
- Reproducción: enfocar un botón `.widget-edit` y ejecutar la misma carga usada por
  el refresco periódico (`loadDashboard`).
- Resultado: el elemento activo pasa de `widget-edit` a `BODY`.
- Impacto: interrumpe la navegación por teclado cuando se recrean las tarjetas.
- Recomendación: actualizar componentes por ID conservando el elemento enfocado,
  o restaurar foco de forma estable tras reemplazarlo. No interrumpir tareas activas.
- Siguiente trabajo sugerido: `$impeccable harden`.

**F03 — El fallo de actualización deja información previa sin aviso persistente.**

- Ubicación: `static/app.js:9`, `loadDashboard` y manejadores de actualización.
- Reproducción: devolver 503 al actualizar el dashboard.
- Resultado: aparece un toast, pero se oculta a los 5,5 s; las tarjetas anteriores
  permanecen y no aparece una advertencia persistente de fallo de actualización.
- Impacto: se puede confundir una vista sin actualizar con una consulta correcta.
  La hora de última métrica ya existe y mitiga parcialmente el problema.
- Recomendación: conservar los datos con un aviso persistente de actualización
  fallida, hora del último refresco correcto y acción de reintento.
- Siguiente trabajo sugerido: `$impeccable harden`.

## Oportunidades visuales: no son regresiones

**D01 — P2: tema claro y oscuro con selector.** Es una preferencia nueva del usuario.
La app actual no tiene selector ni variantes completas; emular preferencia oscura
mantiene el mismo fondo claro. Definir tokens para superficie, texto, bordes y
estados; respetar preferencia del sistema cuando no haya elección guardada y
persistir la selección. Validar todos los diálogos, tablas y widgets en ambos temas.

**D02 — P3: unificar el lenguaje visual.** Las tarjetas oscuras, con esquinas de
23 px y degradado, contrastan con tablas blancas de esquinas menores y acento turquesa.
Su origen responde a la referencia anterior de widgets y no es un fallo funcional.
Para Braun/Nothing, proponer superficies más uniformes, números legibles, bordes
contenidos, espaciado consistente y acentos operativos. Evitar convertir toda la
interfaz en una imitación ornamental de un teléfono.

## Qué conviene conservar

- Navegación principal pequeña y predecible, con acciones nombradas.
- Separación explícita entre capacidad de inventario y métricas medidas.
- Estados con texto; se aclara que error SSH no equivale a servidor apagado.
- Campos con etiquetas, foco visible y regiones de estado/error existentes.
- Revisión previa y confirmación en importación, organización y eliminación.
- Selección conservada entre filtros y advertencia de equipos fuera del filtro.
- Valores cero visibles y datos ausentes diferenciados mediante guiones.

## Orden propuesto para corregir

1. Contraste, nombres de diálogos y continuidad del foco.
2. Mensajes de vacío y error; claridad del alta manual.
3. Tokens y selector de tema, con una muestra de inventario y widget para acordar
   la dirección Braun/Nothing antes de extenderla al resto de la interfaz.
4. Adaptación móvil y legibilidad; regresión de los recorridos funcionales y
   comprobaciones en ambos temas.

Las correcciones y un eventual rediseño quedan pendientes de la siguiente tarea.
