---
name: "q_Inv"
description: "Inventario y monitoreo de infraestructura; precisión operativa en claro y oscuro."
colors:
  light-canvas: "#f3f2ee"
  light-surface: "#fff"
  light-subtle: "#eeeee9"
  light-text: "#202321"
  light-muted: "#535b55"
  light-border: "#c8cdc6"
  light-control: "#fff"
  light-hover: "#e8ebe5"
  light-accent: "#242824"
  light-on-accent: "#fff"
  light-focus: "#255dbb"
  light-positive: "#17673b"
  light-warning: "#785000"
  light-danger: "#a32524"
  light-positive-bg: "#e5f2e9"
  light-warning-bg: "#fff0cd"
  light-danger-bg: "#fff0ed"
  light-track: "#d7dfd6"
  dark-canvas: "#141715"
  dark-surface: "#1d211e"
  dark-subtle: "#272d28"
  dark-text: "#f0f1eb"
  dark-muted: "#b4bdb4"
  dark-border: "#4b554c"
  dark-control: "#1d211e"
  dark-hover: "#333d34"
  dark-accent: "#eceee7"
  dark-on-accent: "#1b211c"
  dark-focus: "#9abfff"
  dark-positive: "#87dba4"
  dark-warning: "#f1cd79"
  dark-danger: "#ffafa6"
  dark-positive-bg: "#183423"
  dark-warning-bg: "#3b301a"
  dark-danger-bg: "#3d2421"
  dark-track: "#3e4b41"
  brand-dot: "#c3352b"
typography:
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "28px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.025em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "13px"
  compact-resource:
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.1
  metric:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.2
rounded:
  badge: "4px"
  field: "5px"
  button: "6px"
  table: "8px"
  dialog-widget: "12px"
spacing:
  control-gap: "8px"
  action-gap: "10px"
  metric-gap: "12px"
  section-gap: "20px"
  card-inset: "12px"
  dialog-inset: "28px"
  page-inset: "32px"
components:
  button-primary:
    backgroundColor: "{colors.light-accent}"
    textColor: "{colors.light-on-accent}"
    rounded: "{rounded.button}"
    padding: "9px 14px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.light-control}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.button}"
    padding: "9px 14px"
  button-danger:
    backgroundColor: "{colors.light-danger-bg}"
    textColor: "{colors.light-danger}"
    rounded: "{rounded.button}"
    padding: "9px 14px"
  field:
    backgroundColor: "{colors.light-control}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.field}"
    padding: "10px 11px"
    height: "42px"
  badge:
    backgroundColor: "{colors.light-subtle}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  navigation-active:
    backgroundColor: "{colors.light-subtle}"
    textColor: "{colors.light-text}"
    padding: "12px"
  server-widget:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.table}"
    padding: "12px"
---

# Design System: q_Inv

## Overview

**Creative North Star: "Instrumentación operativa"**

q_Inv interpreta las referencias Braun/Nothing autorizadas mediante superficies cálidas o carbón, divisores finos, tinta legible y controles familiares. La densidad sirve al trabajo diario de infraestructura y a la comparación de datos; el español y la lectura precisa son compromisos duraderos.

El sistema documenta la implementación final en HTML/CSS/JavaScript. La dirección Operate se construyó directamente en código, sin comp raster ni seed: esa omisión está declarada en el contrato de dirección y no equivale a una aprobación de assets inexistentes.

**Key Characteristics:**

- Superficies planas con contraste tonal.
- Cifras tabulares y estados escritos.
- Tema claro, oscuro o del sistema.
- Controles reconocibles y foco visible.

## Colors

La paleta es neutral, ligeramente cálida en claro y verdosa en carbón; los estados aportan color funcional. Los tokens del frontmatter son normativos: el prefijo `light-` corresponde a `:root` y `dark-` a `:root[data-theme=dark]`; el sufijo conserva el nombre de la variable CSS real.

### Primary

`accent` y `on-accent` forman el botón principal y la selección: tinta sobre claro, superficie clara sobre oscuro. `focus` identifica navegación por teclado. El punto `brand-dot` es una firma estática del logotipo, no un estado ni un segundo acento de acciones.

### Neutral

`canvas` es el fondo; `surface` contiene navegación, tablas, widgets y diálogos; `subtle` agrupa encabezados, selección y avisos neutrales. `text` y `muted` distinguen jerarquía sin ocultar información; `border` delimita; `control` y `hover` sirven a campos y botones; `track` conserva el recorrido de los indicadores.

Los pares `positive` / `positive-bg`, `warning` / `warning-bg` y `danger` / `danger-bg` describen éxito, atención y error/destrucción. Conexión correcta es positiva, error SSH es peligro y datos antiguos son advertencia. Pendiente, sin configurar y pausado usan texto neutral. Los indicadores de recursos cambian a advertencia desde 75 % y peligro desde 90 %. La ausencia usa raya y texto de sin datos, con el recorrido neutral.

**The Semantic Color Rule.** El color de estado acompaña una etiqueta o un valor; no sustituye el significado textual.

El selector ofrece Claro, Oscuro y Sistema en acceso y espacio de trabajo. `qinv-theme` persiste en localStorage, sincroniza pestañas mediante `storage` y sigue `prefers-color-scheme` cuando se elige Sistema; el valor inicial es Sistema. Storage bloqueado no impide cambiar la apariencia. La propiedad `color-scheme` acompaña el tema para controles nativos.

## Typography

**Body Font:** sans del sistema definida en el frontmatter; no se descarga una fuente externa.

La jerarquía operativa usa títulos compactos, etiquetas legibles y números tabulares en tablas, resúmenes y recursos. El titular de página se reduce a 25 px en móvil. Los títulos de widget usan 14 px; diálogo 21 px (20 px en móvil); cuerpo de tabla y etiquetas 13 px; texto auxiliar y badges 12 px. El resumen usa 30 px. Acceso tiene una excepción de 36 px, reducida a 32 px en móvil. El logotipo es texto de 28 px y peso 750, no un estilo de titular reutilizable. La marca técnica de SO conserva 10 px como abreviatura auxiliar, sin albergar datos esenciales.

Los párrafos tienen interlineado 1.6; los detalles operativos suelen usar 1.5. La descripción de página limita su ancho a 65ch y los vacíos a 55ch. Los pesos 600–700 distinguen acciones y encabezados; no hay escala tipográfica de marketing.

**The Operational Type Rule.** La sans del sistema es tipografía de trabajo; las métricas usan cifras tabulares, sin introducir una fuente display decorativa.

## Layout

En escritorio la navegación fija mide 218 px; el contenido compensa ese ancho. Cabecera mínima de 76 px; contenido con 34 px verticales y 32 px laterales. El resumen es una banda de cuatro columnas con divisores. Widgets: rejilla auto-fill con mínimo de 250 px limitado al ancho disponible y separación de 12 px. Cuatro columnas en un escritorio de 1440 px; una columna en móvil. CPU/RAM/disco usan porcentajes y barras; red/E/S muestran tasas compactas. Se muestran hasta 48 equipos por página.

A 1180 px se apilan título/acciones, herramientas y barra de selección; filtros organizativos pasan a dos columnas. A 850 px la navegación deja de ser fija, envuelve arriba y el resumen pasa a dos columnas; los laterales del contenido son 22 px. A 600 px los laterales son 18 px, los formularios y filtros organizativos pasan a una columna y red/E/S bajan bajo los tres indicadores. Las acciones se envuelven; los botones de diálogo comparten ancho y su franja queda sticky.

Las tablas conservan columnas legibles con scroll local (alto máximo 560 px), encabezado sticky y acción final sticky en inventario. En tamaños pequeños se muestra la indicación de desplazamiento; el contenedor tiene nombre accesible y foco. No resolver una tabla ancha provocando scroll global. El diálogo limita su ancho al viewport menos 32 px y su altura al viewport dinámico; medidas nominales: 760 px general, 540 px catálogo, 970 px edición masiva y 820 px eliminación. Acceso limita el formulario a 420 px.

## Elevation & Depth

Las superficies de reposo son planas: fondo, borde fino y tono organizan la información. Los diálogos son la única elevación estructural, con sombra suave distinta por tema y backdrop de `rgb(15 22 18 / 58%)`. Sus valores completos viven en el sidecar. No se usa esta excepción para apilar tarjetas.

**The Modal Depth Rule.** La sombra aísla una tarea modal; las tarjetas permanecen planas y se separan con borde y tono.

## Shapes

Geometría funcional con bordes de 1 px: esquinas discretas en campos y botones, más amplias en contenedores y diálogos, según frontmatter. Los puntos de estado son círculos de 6 px y la firma del logotipo de 7 px. Los badges son rectángulos suaves, no cápsulas. Los indicadores de recursos son barras SVG horizontales con viewBox 100 × 4 y extremos de 2 px; el porcentaje permanece como texto legible de 20 px.

## Components

### Buttons

Primario de contraste neutral, secundario con borde, peligro con par semántico y acciones textuales transparentes. Mínimo general de 40 px; edición y selector de tema 36 px. El hover secundario usa `hover`, el primario reduce brillo a .9. Deshabilitado usa opacidad .55 y cursor no permitido. Transición de fondo de .16s ease-out, anulada con `prefers-reduced-motion`. Conservar foco de 3 px separado 3 px del borde.

### Inputs / Fields

Fondos `control`, borde `border`, tinta y caret `text`; placeholder `muted` opaco. Altura mínima 42 px, relleno según frontmatter. Labels visibles con separación 8 px. Checkboxes nativos de 24 px con acento del tema. Los errores se escriben cerca de la tarea en peligro y usan `role=alert`; los procesos y resultados usan `role=status` o región live polite.

### Navigation

Icono y etiqueta, selección tonal y mayor peso, `aria-current=page`. En móvil envuelve y mantiene etiquetas completas. SVG inline de 20 px, trazo currentColor de 1.7, extremos/uniones redondos, sin relleno; en navegación móvil 17 px. Cierre y refresco usan SVG creados en JavaScript, `aria-hidden=true`, y nombre accesible en el botón. No heredar los glifos de cierre provisionales del HTML: el runtime los sustituye.

### Chips

Badges y tipo de servidor usan fondo `subtle`, texto `text` y esquinas pequeñas. Las etiquetas largas se envuelven en inventario. Los chips informativos no aparentan botones; las pestañas de catálogo son botones con `aria-pressed` y selección de contraste principal.

### Cards / Containers

Tablas y ajustes comparten superficie y borde fino, sin sombra. Widgets compactos con radio de 8 px y relleno de 12 px; nombre y estado/IP, tres recursos, tasas de red/E/S y acciones en una línea. «Detalles» conserva temperatura, actividad, carga, acumulados, error completo, contexto y fecha de consulta. La apertura y el foco se conservan durante el refresco. Los indicadores incluyen role=img y nombre con porcentaje o sin datos. Medición de referencia a 1440 px: aproximadamente el 25 % del área de la tarjeta de v0.4.0; en móvil se prioriza legibilidad.

### Dialogs and feedback

Usar diálogo nativo con nombre por `aria-labelledby`, título de tarea y botón de cierre con label. Formularios y acciones conservan foco; previsualización y confirmación hacen visibles los efectos antes de guardar o eliminar. El toast usa contraste principal, posición inferior centrada, ancho limitado al viewport y `role=status`. Vacíos incluyen título, explicación y acción pertinente; un error de actualización conserva datos previos y ofrece reintento. La calidad objetivo es contraste normal mínimo 4.5:1; no reducir etiquetas ni ocultar información esencial para ganar densidad.

## Do's and Don'ts

### Do:

- Do conservar los pares semánticos de cada tema y el foco visible.
- Do mostrar unidades, capacidades y métricas como conceptos distintos.
- Do representar ausencia con raya y texto explicativo; cero sigue siendo una medición válida.
- Do mantener etiquetas accesibles en iconos de acción y confirmación en operaciones masivas.

### Don't:

- Don't usar un error SSH como prueba de que el servidor está apagado.
- Don't convertir tarjetas en capas de sombras decorativas.
- Don't reemplazar los iconos SVG de acción por glifos o depender solo del color.
- Don't guardar la preferencia de apariencia como configuración del servidor.
