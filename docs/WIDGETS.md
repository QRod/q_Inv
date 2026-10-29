# Widgets del dashboard

Cada cuenta dispone de una sola vista personalizable. En **Dashboard → Personalizar** se eligen los widgets, su orden y la visibilidad de las tarjetas de servidores. Las preferencias se guardan en el servidor y se conservan al iniciar sesión desde otro navegador. El tema claro/oscuro sigue siendo una preferencia del navegador.

Los filtros de grupo, ambiente y tipo de equipo se aplican a los widgets, los cuatro recuentos superiores y las tarjetas. La búsqueda y el selector de estado junto a las tarjetas solo filtran esas tarjetas. Todos los resultados respetan los grupos autorizados de la cuenta. Si se revoca acceso a un filtro guardado, se retira y se muestra un aviso.

Pulsar un recuento abre el inventario con los equipos correspondientes. El botón para limpiar el filtro del análisis permite volver a consultar el inventario completo autorizado.

## Indicadores disponibles

| Widget | Lectura y uso |
|---|---|
| Sistemas operativos | Distribución del SO registrado, por familia o familia y versión. Permite identificar concentración tecnológica. |
| Ciclo de soporte estándar | Equipos fuera de ciclo, próximos al fin, dentro del ciclo o por verificar. Horizonte de 30, 90, 180 o 365 días. Cada equipo conserva fecha, criterio y fuente del fabricante cuando están disponibles. |
| Cobertura de monitoreo | Consultas recientes correctas, errores SSH, datos antiguos, pendientes, pausados y conexiones sin configurar. Ayuda a detectar zonas sin observación. |
| Presión de recursos | Últimas muestras recientes que alcanzan los umbrales de CPU, RAM o disco raíz; umbrales configurables entre 1 y 100 %. El total de afectados no duplica equipos. |
| Capacidad asignada por aplicación | CPU, RAM y disco inventariados, separados entre físicos y virtuales. Los servidores con varias aplicaciones se agrupan en Compartidos y se cuentan una sola vez. |
| Calidad del inventario | Falta de SO, clasificación, ambiente, responsable o capacidad; también versiones y ciclos pendientes de verificar. Las categorías pueden coincidir. |

La presión de recursos usa muestras correctas y recientes; un recurso ausente, una consulta fallida o datos antiguos no equivalen a consumo cero. Un equipo con al menos un recurso válido puede evaluarse parcialmente. Disco corresponde al sistema de archivos raíz `/`. Los datos siguen el intervalo de recolección configurado; actualizar la vista no fuerza una conexión SSH.

La cobertura describe el estado del recolector, no un SLA ni disponibilidad real del servicio. La capacidad asignada no representa espacio libre del hipervisor ni ahorro potencial. Los valores ausentes se excluyen de las sumas y aparecen en Calidad del inventario.

## Referencia de soporte

El catálogo local `catalogs/os-lifecycle.json` fue revisado el **29 de octubre de 2026** y se distribuye con las versiones de q_Inv. La evaluación usa la fecha UTC actual. Un aviso señala catálogos con más de 180 días desde su revisión; no se consultan fabricantes automáticamente ni se envía el inventario a servicios externos.

La clasificación considera el ciclo regular del fabricante y excluye coberturas adicionales adquiridas:

- **RHEL:** ciclo regular, sin EUS/ELS. Una fecha futura de versión principal no confirma que una versión menor siga recibiendo mantenimiento estándar. La referencia distingue el caso final 8.10; otras versiones menores no validadas quedan por verificar. Fuentes: [política de actualizaciones](https://access.redhat.com/support/policy/updates/errata), [ciclos de producto](https://access.redhat.com/product-life-cycles), [RHEL 5 y 6](https://access.redhat.com/articles/4038291) y [RHEL 7](https://access.redhat.com/articles/7005471).
- **Windows Server:** ciclo fijo ordinario, incluido Extended Support de Microsoft; ESU adicional queda excluido. Fuentes: [versiones de Windows Server](https://learn.microsoft.com/en-us/windows/release-health/windows-server-release-info), [2008](https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2008) y [2012](https://learn.microsoft.com/en-us/lifecycle/products/windows-server-2012).
- **Ubuntu:** mantenimiento de seguridad estándar, sin Ubuntu Pro/ESM. No se heredan fechas a distribuciones derivadas ni sabores. Fuente: [ciclo de Ubuntu](https://ubuntu.com/about/release-cycle).
- **AIX:** nivel Technology Level cuando está identificado. El fin de correcciones de un TL puede requerir actualizar ese nivel y no sustituir la versión principal. Una fecha todavía no anunciada queda por verificar. Fuentes: [niveles AIX](https://www.ibm.com/support/pages/aix-support-lifecycle-information) y [AIX 7.1](https://www.ibm.com/support/pages/node/1125435).
- **Solaris:** Premier Support, sin Extended ni Sustaining Support. SunOS 5.11 no identifica por sí solo Solaris 11.4. Fuente: [Oracle Lifetime Support](https://www.oracle.com/us/support/library/lifetime-support-hardware-301321.pdf).

Cuando la fuente publica solo el mes, la interfaz conserva esa precisión; durante el mes final indica Por verificar. Descripciones ambiguas como «2016 o posterior», versiones sin referencia y niveles incompletos no reciben una clasificación positiva automática. Se evalúa el texto registrado en inventario; no se certifican parches instalados, suscripciones, hardware elegible ni cobertura contractual.

## Integración y permisos

`GET /api/dashboard/widgets` requiere sesión y devuelve preferencias, catálogos autorizados e indicadores calculados después de aplicar el ámbito de acceso. Los identificadores asociados a los recuentos permiten abrir el inventario correspondiente.

`POST /api/dashboard/preferences` requiere sesión y CSRF. Acepta exactamente `revision` (entero) y `config`, con las claves:

```json
{
  "revision": 0,
  "config": {
    "widgets": ["os_distribution", "support_lifecycle", "monitoring_coverage"],
    "show_servers": true,
    "group_id": null,
    "environment_id": null,
    "server_type": "all",
    "os_grouping": "version",
    "support_horizon": 180,
    "cpu_threshold": 85,
    "memory_threshold": 85,
    "disk_threshold": 85
  }
}
```

Otros widgets: `resource_pressure`, `allocated_capacity`, `inventory_quality`. `server_type` admite `all`, `virtual`, `physical`; `os_grouping`, `family` o `version`. La lista de widgets puede estar vacía y no admite duplicados. Los filtros deben pertenecer a los catálogos autorizados.

Cada cuenta modifica únicamente sus preferencias, incluso con rol Lector; esto no concede escritura sobre inventario o configuración global. Un guardado incrementa la revisión y registra `dashboard.preferences` en auditoría. Si otra pestaña guardó una revisión posterior, responde 409; cerrar y abrir Personalizar carga la versión vigente. La migración agrega una tabla de preferencias sin modificar métricas ni clasificación de servidores.
