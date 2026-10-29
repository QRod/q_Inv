# Guía de uso

## Dashboard

El dashboard reúne tarjetas compactas por servidor con CPU, memoria, disco raíz y tasas de red y E/S. **Detalles** amplía uptime, carga, acumulados, errores y fecha de consulta. La búsqueda y el filtro de estado permiten localizar equipos; el refresco conserva los detalles abiertos y el foco del teclado.

El botón de tema alterna entre claro y oscuro, con preferencia guardada en el navegador. Antes de elegir, sigue la apariencia del sistema. Los datos ausentes se muestran con un guion y se distinguen de una medición de cero.

Al pulsar el nombre de una tarjeta se abre la [ficha e historial](HISTORIAL.md), con estado registrado, inventario y gráficas interactivas de recursos.

**Personalizar** permite elegir y ordenar widgets, ajustar filtros y umbrales y mostrar u ocultar tarjetas. Las preferencias pertenecen a cada cuenta. Consulta [Widgets y soporte](WIDGETS.md) para interpretar los indicadores.

## Importar desde RVTools

Una cuenta administradora puede cargar un archivo `.xlsx` desde **Importar RVTools** y pulsar **Validar y previsualizar**. La hoja `vInfo` debe contener el nombre de la VM y un UUID; se admiten hasta 20 MB y 10 000 filas. Las filas inválidas bloquean la confirmación. La vista previa expira a los 30 minutos.

La conciliación utiliza `VM UUID`, `UUID` o `Instance UUID`. Repetir una importación actualiza los mismos registros y conserva sus grupos, aplicaciones y demás clasificaciones. Los otros campos de inventario se reemplazan por los de la exportación; un campo ausente queda vacío. RAM y disco se convierten de MiB a GiB desde `Memory` y `Provisioned MiB`. Las tarjetas e IPs se leen de `vNetwork` cuando está incluida. `vDisk` no se procesa.

Revisar los encabezados y la vista previa antes de confirmar. Las capacidades importadas describen el inventario y no representan consumo en tiempo real.

## Tarjetas de red y direcciones IP

La importación reconoce las variantes `IPv4 Address`, `IPv6 Address` e `IP Address` de `vNetwork`. Cada tarjeta conserva nombre, tipo de adaptador, red, switch, MAC, conexión actual, conexión al iniciar y todas sus IPs reportadas. Las direcciones repetidas se normalizan; una tarjeta sin IP también se conserva.

Las filas se relacionan con `vInfo` por VM UUID. Si falta ese identificador en `vNetwork`, solo se admite un nombre de VM único dentro del archivo. Una coincidencia ambigua o un UUID contradictorio bloquea la confirmación. La compatibilidad se basa en encabezados reconocidos; una exportación con encabezados distintos requiere adaptar el lector. La información disponible depende de lo que VMware Tools y RVTools hayan reportado.

La vista previa permite expandir tarjetas e IPs antes de importar. En Inventario, expandir el resumen de red bajo el nombre; también puede consultarse en la edición y en Detalles del dashboard. La búsqueda considera IPs secundarias, red, adaptador y MAC.

La IP principal define el destino SSH. Si ya existe una credencial guardada, la importación conserva ese destino y muestra por separado la IP principal reportada por RVTools; no prueba conexiones con las IPs adicionales. Para cambiarlo, editar la IP principal y revisar las credenciales del nuevo destino.

Usar una exportación completa: una hoja filtrada puede omitir tarjetas. Revisar el resumen de red antes de confirmar. Una reimportación con `vNetwork` reemplaza las tarjetas de los servidores conciliados por las reportadas en el archivo; no las acumula. Si el archivo solo contiene `vInfo`, se pueden leer columnas `NIC #1`, `NIC #2`, etc. cuando existen. Sin columnas de tarjetas ni `vNetwork`, se conservan las interfaces guardadas. Una hoja de red válida sin filas para una VM indica que no hay tarjetas reportadas para ella.

Límites: 100 000 filas en `vNetwork`, 128 tarjetas por VM, 128 IPs por tarjeta y 1024 IPs por VM. Las direcciones o MAC inválidas se muestran como errores de validación y bloquean la importación. Las IPs IPv6 locales al enlace se conservan como inventario y no se seleccionan automáticamente para SSH.

## Organización del inventario

La sección **Organización** permite crear, renombrar y eliminar entradas de cinco catálogos: grupos, aplicaciones, ambientes, responsables y etiquetas. Una entrada con servidores asignados no puede eliminarse: primero hay que reasignarlos. Los identificadores son estables y renombrar una entrada conserva sus relaciones.

Cada servidor admite varios grupos y aplicaciones, un ambiente, un responsable principal y varias etiquetas. El responsable puede representar una persona o un equipo, con contacto opcional; es independiente de las cuentas de acceso.

Al actualizar, los grupos y aplicaciones que ya existían como texto se convierten en entradas compartidas sin modificar identificadores de servidores, credenciales o historial de métricas. Los nombres equivalentes por mayúsculas/minúsculas se agrupan. Se crean ambientes iniciales **Producción**, **Pruebas** y **Desarrollo**, pero ningún servidor recibe un ambiente por suposición. Las entradas eliminadas no se recrean al reiniciar.

Para asignar datos a un equipo, abre **Inventario → Editar → Organización del servidor**. Los filtros permiten buscar por grupo, aplicación, ambiente, responsable, etiqueta y valores sin asignar. La búsqueda libre y la búsqueda del dashboard también consideran todas las asignaciones, incluidos los grupos y aplicaciones secundarios.

Para organizar varios equipos:

1. Selecciona las filas o todos los servidores del filtro actual. La selección se conserva al cambiar filtros y se indica si hay seleccionados fuera de la vista.
2. Pulsa **Organizar seleccionados** y marca únicamente los campos que quieras modificar.
3. Selecciona sus valores. Se reemplazan las listas de grupos, aplicaciones o etiquetas; un campo marcado sin valores elimina esa asignación. Los campos sin marcar se conservan.
4. Pulsa **Previsualizar cambios**, revisa los nombres y los valores anteriores/nuevos, y confirma.

Cada operación admite hasta 500 servidores, se aplica como una transacción y deja un registro de auditoría. La vista previa dura 15 minutos, pertenece a la cuenta que la creó y solo puede confirmarse una vez. Si el inventario o los nombres de catálogo cambian entre la vista previa y la confirmación, la operación se rechaza y hay que previsualizar de nuevo.

La importación RVTools conserva toda la clasificación existente al conciliar por UUID. Las ediciones masivas no modifican contraseñas SSH, frecuencia de consultas, métricas ni campos técnicos del servidor. Los campos de texto antiguos `group_name` y `application` siguen representando la primera asignación por orden de nombre para mantener compatibilidad con clientes anteriores; los clientes nuevos deben usar los identificadores de `organization` y las listas de asignaciones.

## Eliminar servidores seleccionados

En Inventario, selecciona las filas y pulsa **Eliminar seleccionados**. La confirmación muestra todos los equipos afectados, incluidos los seleccionados fuera del filtro actual, y sus credenciales y muestras asociadas. La eliminación requiere marcar la confirmación explícita y pulsar **Eliminar definitivamente**.

La operación elimina únicamente los registros de q_Inv, sus credenciales SSH, métricas y asignaciones. No se conecta a los servidores remotos ni los elimina de VMware. Los catálogos se conservan y queda un registro de auditoría con los identificadores eliminados, sin contraseñas. Los respaldos anteriores permanecen intactos; una importación posterior de RVTools puede volver a crear los equipos.

Las confirmaciones expiran en 10 minutos, pertenecen a la cuenta que las creó y no pueden reutilizarse. Si cambia un equipo mientras se revisa la selección, se rechaza toda la operación. Los identificadores eliminados no se reutilizan, y una consulta de métricas en curso no puede volver a crear el registro eliminado.

## Conexión SSH, credenciales y recolección

Una cuenta con permisos de escritura puede configurar la conexión en **Agregar servidor** o **Editar → Conexión SSH y monitoreo**. Allí introduce IP, puerto (22 por defecto), usuario y contraseña. Usa **Conectar y descubrir** para verificar la huella SSH y completar el inventario. Al pulsar **Guardar servidor**, se guardan los datos y la credencial cifrada. La casilla **Recopilar métricas automáticamente** permite activar o pausar las consultas.

Al editar una conexión ya guardada, la contraseña no se devuelve al navegador. Déjala vacía para conservarla o escribe una nueva para reemplazarla. Cambiar de usuario exige introducir contraseña. El descubrimiento puede utilizar la credencial guardada solo con la misma IP, puerto y usuario. No se usa sudo ni se instalan programas en el servidor consultado.

### Cifrado y clave maestra

- La contraseña SSH se almacena como un token Fernet (cifrado autenticado), separado de los metadatos de conexión. No se registra la contraseña en claro, no se envía en las respuestas API y no se muestra al editar.
- `QINV_KEY_FILE` indica la ubicación de la clave. En desarrollo se crea `secrets/credentials.key` con permisos 600; el directorio está excluido de Git. Si existen credenciales y falta la clave, el arranque falla en lugar de generar una clave incompatible.
- En instalaciones administradas la clave se encuentra en `/etc/q-inv/credentials.key`, propiedad de root y con permisos 600. systemd 247+ la entrega al servicio mediante `LoadCredential`; la aplicación la lee desde `/run/credentials/`. En systemd anterior el instalador utiliza un archivo de lectura exclusiva para el usuario del servicio, protegido por los permisos de `/etc/q-inv` y la unidad systemd.
- Una copia aislada de SQLite no incluye la clave. El comando `q-inv-admin --backup` conserva base y clave juntas; ambas son necesarias para restaurar las conexiones. No se debe reemplazar la clave sin migrar antes las contraseñas cifradas.
- La confianza SSH se conserva en `data/ssh_known_hosts`. La primera conexión requiere verificar la huella; un cambio posterior de clave se rechaza y requiere revisión del administrador.

### Métricas y dashboard

El proceso de la aplicación ejecuta un recolector con hasta seis consultas simultáneas, independiente del navegador. El intervalo global es de 5 minutos y la retención de 60 días, ambos editables en Configuración. Las consultas fallidas también quedan registradas. El historial vencido se limpia aproximadamente cada hora. Una solicitud manual en la tarjeta adelanta la siguiente consulta; **Actualizar vista** solo vuelve a leer los datos guardados.

La vista se actualiza cada 20 segundos mientras permanece visible, con búsqueda, filtros de estado y hasta 48 tarjetas por página. Muestra estados **Conectado**, **Error SSH**, **Datos antiguos**, **Pendiente**, **Sin configurar** y **Pausado**. Un error SSH no demuestra que el equipo esté apagado. Si una muestra supera el doble del intervalo configurado (mínimo 2 minutos), se marca como antigua.

Para Linux se consultan CPU (muestra de aproximadamente 1 segundo), memoria disponible, uso y capacidad del sistema de archivos raíz `/`, uptime, carga, un sensor térmico si existe, tráfico de interfaces excepto loopback y E/S de discos base visibles. Red y E/S muestran tasas en bytes por segundo y contadores acumulados del sistema. Interfaces virtuales o capas de almacenamiento pueden afectar la interpretación de los contadores. Los datos no disponibles se muestran con un guion, sin inventar ceros.

El descubrimiento de inventario incluye consultas para Linux, AIX y SunOS. Linux intenta leer UUID y detectar virtualización cuando los permisos lo permiten. Grupo, aplicación, host VMware y clúster siguen siendo manuales o procedentes de RVTools. La capacidad descubierta mediante `lsblk` puede incluir varios discos; es diferente del uso de `/` mostrado en el dashboard.

La recolección periódica está implementada inicialmente para Linux. Las consultas de descubrimiento AIX/SunOS se verifican con datos sintéticos; la validación en RHEL 5/6/7/8, AIX 7 y SunOS 11 sigue pendiente. Windows requiere su recolector específico. La conexión requiere algoritmos SSH modernos; los equipos que solo aceptan SHA-1 necesitan actualizar su configuración SSH.

## Generar una muestra anonimizada de RVTools

Ejecuta el comando en tu propio equipo, con la ruta al archivo original:

```sh
.venv/bin/python server.py --anonymize "/ruta/RVTools-original.xlsx" "/ruta/RVTools-muestra.xlsx"
```

El comando crea un libro nuevo con hasta 100 registros y solo una hoja `vInfo`. Reemplaza nombres, UUID, IP, hosts y clústeres; utiliza SO, capacidades y estado sintéticos. No copia otras columnas, hojas, fórmulas ni metadatos del libro original. No modifica el original ni sobrescribe un destino existente. Revisa la copia en Excel o LibreOffice antes de compartirla. Si el formato no se reconoce, el comando informa el error y será necesario ajustar el lector.

La muestra sirve para verificar encabezados y el flujo de carga; al sustituir valores no permite comprobar los casos particulares de tus sistemas operativos o capacidades originales. El archivo original puede permanecer en tu equipo.

## Permisos y administración

La visibilidad del inventario depende del rol y los grupos autorizados. La importación, la eliminación, los catálogos y las opciones globales requieren permisos de administrador. Consultar [Acceso y operación](ACCESO-Y-OPERACION.md) para gestionar usuarios, auditoría, versiones y respaldos.
