# Ficha e historial del servidor

Pulsar el nombre de un servidor en una tarjeta del dashboard abre su ficha. La vista reúne el estado de la última consulta, la fecha de medición, recursos registrados, inventario, clasificación y tarjetas de red.

Los accesos **Ver estado**, **Ver gráficas** y **Ver inventario** permiten ir directamente a cada sección.

**Actualizar datos** vuelve a leer los datos guardados; no inicia una nueva conexión SSH. Las consultas se recolectan con el intervalo configurado. El enlace **Volver al dashboard** conserva la búsqueda de tarjetas. Una ficha también puede abrirse mediante `#server/ID`, siempre con una sesión y permisos para ese servidor.

## Gráficas

- CPU, RAM y disco raíz: porcentaje promedio y máximo de cada intervalo.
- Red: tasas promedio de bytes recibidos y enviados por segundo.
- E/S: tasas promedio de lectura y escritura de discos por segundo.
- Consultas SSH: resultados correctos, fallidos, parciales o sin muestras por intervalo.

El porcentaje de consultas correctas utiliza únicamente las consultas registradas. No mide disponibilidad real, tiempo encendido ni periodos sin recolección. Los periodos vacíos no se cuentan como éxito ni como fallo.

Los rangos predefinidos son 1 hora, 6 horas, 24 horas, 7 días, 30 días y 60 días. **Fechas específicas** permite elegir otro periodo en la zona horaria del navegador. Los datos quedan limitados a la retención configurada; la vista informa si recorta el rango por ese motivo.

## Interpretación

Cada respuesta contiene como máximo 720 intervalos. El tamaño del intervalo es al menos la frecuencia actual de recolección y crece para rangos largos. Los porcentajes conservan el máximo del intervalo para mostrar picos junto con el promedio. Las tasas de red y E/S son promedios de las muestras de tasa, no contadores acumulados ni volúmenes transferidos.

Las muestras fallidas y los recursos no disponibles no se convierten en cero. Los huecos de las curvas indican que no hay mediciones válidas en ese intervalo. Una gráfica sin mediciones lo indica expresamente. Un intervalo con consultas correctas y fallidas se marca como parcial en la banda SSH; los promedios utilizan solo las mediciones válidas de consultas correctas.

Mover el cursor sobre una gráfica o utilizar el control **Explorar una muestra agregada** permite consultar fecha, resultados y valores. El control admite las flechas del teclado. La tabla **Consultar datos de las gráficas** ofrece la misma información en formato tabular. Las fechas se presentan en la zona horaria del navegador y los ejes identifican porcentaje o bytes por segundo.

## Acceso y datos

La ficha y el historial respetan los mismos grupos y roles que el inventario. Un lector puede consultar sus servidores; los datos de otros grupos no están disponibles mediante sus enlaces o API. Los cambios de sesión limpian la ficha y sus gráficas.

El historial muestra muestras que ya existen en la base de datos; instalar esta versión no crea métricas anteriores. Las gráficas se generan en el navegador con recursos locales, sin enviar datos a un servicio externo.

## API de consulta

- `GET /api/servers/ID`: `server` con inventario y red; `current` con el estado y la última muestra. No devuelve credenciales SSH.
- `GET /api/servers/ID/history?hours=24`: resumen e intervalos agregados.
- `GET /api/servers/ID/history?from=EPOCH&to=EPOCH`: rango de fechas en segundos Unix, de al menos un minuto, hasta diez años y dentro de la retención disponible.

La respuesta histórica contiene `from`, `to`, `requested_from`, `bucket_seconds`, `interval_minutes`, `retention_days`, `samples`, `successful`, `failed`, `success_percent` y `points`. Cada intervalo contiene `at`, `until`, recuentos de consultas, `values` con promedios y `maxima` con máximos. Los recursos sin medición se representan con `null`; `success_percent` también es `null` si no existen consultas. Los rangos inválidos devuelven 400; una sesión ausente, 401; un servidor fuera del ámbito, 403.
