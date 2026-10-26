# q_Inv

Inventario web de servidores físicos y virtuales para una VM Linux, dimensionado inicialmente para unos 500 equipos. Todo el proyecto se mantiene dentro de este directorio.

## Primera entrega

- Cuentas locales creadas por el administrador, contraseñas con scrypt y sesiones de 8 horas.
- Inventario persistente en SQLite: alta, edición, búsqueda y filtros por tipo y grupo.
- Campos de sistema operativo, capacidad CPU/RAM/disco, IP, UUID, host, clúster, grupo y aplicación.
- Descubrimiento por SSH desde el formulario de alta o edición, con revisión antes de guardar.
- Credenciales SSH persistentes con contraseña cifrada mediante Fernet y clave separada de SQLite.
- Dashboard de tarjetas por servidor: conexión SSH, CPU, RAM, disco raíz, uptime, carga, temperatura disponible, red y E/S.
- Recolección periódica Linux en segundo plano y retención efectiva del historial.
- Importación `.xlsx` de RVTools desde `vInfo`, con vista previa, validación y confirmación transaccional.
- Conciliación por `VM UUID` (o `UUID` / `Instance UUID`), sin duplicar importaciones repetidas. Las filas sin UUID bloquean la confirmación.
- Conservación de grupo y aplicación al actualizar desde RVTools. Los otros campos inventariados se reemplazan por el contenido de la exportación; un campo ausente queda vacío.
- Configuración persistida para recolección cada 5 minutos y retención de 60 días, ambas editables.
- Comando local para generar una muestra reducida y anonimizada de RVTools.

Las capacidades importadas no representan consumo en tiempo real. RAM y disco se muestran en GiB y se convierten desde las columnas `Memory` (MiB) y `Provisioned MiB`. La primera versión solo procesa `vInfo`, no agrega información de `vDisk` ni otras hojas. Los encabezados reconocidos se encuentran en `inventory.py`; su correspondencia con la exportación real está pendiente de validar.

## Instalación en Linux

El instalador independiente descarga una entrega de GitHub Releases, verifica SHA-256, instala dependencias y crea servicios de aplicación y HTTPS. Requiere Linux con systemd, acceso root y Python 3.11+ disponible en los repositorios de la distribución. Código en `/opt/q-inv/releases/`, enlace `current`, datos en `/var/lib/q-inv` y configuración privada en `/etc/q-inv`. No se guardan datos reales en este repositorio.

Para una IP o nombre de la red local, sustituye `SERVIDOR`:

```sh
curl -fsSL https://raw.githubusercontent.com/QRod/q_Inv/v0.2.1/install.sh -o install.sh
less install.sh
sudo bash install.sh --version v0.2.1 --address SERVIDOR --https-port 8443
```

La CA local genera el certificado en cada instalación; no hay certificados ni claves compartidos. El navegador advertirá de la falta de confianza hasta importar la CA local del proxy en el cliente.

Para dominio y certificado público de Let's Encrypt:

```sh
sudo bash install.sh --version v0.2.1 --address app.example.com --tls public --https-port 443 --email admin@example.com
```

El DNS debe apuntar al servidor y los puertos 80/443 estar libres y accesibles desde Internet. Caddy gestiona emisión y renovación. Si ya tienes un proxy compartido o esos puertos ocupados, usa `--proxy external` y configura tu proxy HTTPS contra el backend en loopback; el instalador no modifica ese proxy. El firewall permanece bajo administración del operador.

Después de instalar, crea la primera cuenta de forma interactiva:

```sh
sudo q-inv-admin --create-user admin
```

El comando detiene brevemente la app, solicita la contraseña sin mostrarla, conserva la propiedad de los datos y vuelve a iniciar el servicio. Las instalaciones de Kanban deshabilitan el alta inicial desde la web para que la primera cuenta no pueda ser reclamada por otro visitante.

### Distribuciones y límites

Se prepararon rutas para Debian/Ubuntu/Zorin/Mint (`apt`), Fedora/RHEL/Rocky/AlmaLinux (`dnf`), openSUSE (`zypper`) y Arch/Manjaro (`pacman`). El proxy incluido tiene binarios oficiales verificados para x86_64 y ARM64. No implica compatibilidad con todas las versiones históricas: se exige Python 3.11+, venv y systemd. En Arch se presupone un sistema actualizado; el instalador no hace una actualización global. Alpine/OpenRC y NixOS requieren instalación manual.

La instalación real se valida en Zorin OS. La detección de las otras familias se prueba con archivos os-release; aún no se ha ejecutado la instalación completa en ellas. La configuración de TLS público está preparada, pero su emisión real requiere un dominio y DNS del operador.

### Actualización, respaldo y recuperación

Vuelve a ejecutar el instalador indicando la nueva etiqueta con las mismas opciones (las preferencias de instalación quedan guardadas de forma privada). No se descarga una rama de desarrollo como si fuera una entrega. Cada versión tiene su propio entorno virtual. Antes del cambio se respalda SQLite mediante su API, junto con configuración y unidades anteriores en `/var/backups/q-inv`.

Si el nuevo servicio falla en la comprobación de arranque, el instalador intenta restaurar la versión, base y configuración anteriores. La recuperación manual debe hacerse con el servicio detenido y utilizando el respaldo de la misma fecha; volver solo al código no revierte una migración de datos. Conserva además copias externas de datos y claves; el instalador no sustituye una política de respaldo.

Para migrar una instalación manual, añade `--migrate-from /ruta/a/la/instalacion`. Se copia la base sin borrar el origen. Para q_Inv con credenciales ya cifradas, coloca antes su clave original en `/etc/q-inv/credentials.key` con permisos 600: una clave diferente no recupera las contraseñas anteriores.

Para preparar una entrega desde un checkout limpio:

```sh
python3 scripts/package_release.py v0.2.1
```

El resultado y `SHA256SUMS` quedan en `dist/`, excluido del repositorio. Los paquetes se construyen a partir de archivos versionados, sin bases, claves ni entornos locales. La suma protege la integridad de la descarga; su autenticidad depende del repositorio y del canal HTTPS de GitHub.

## Arranque local o en Linux

Requiere Python 3.11 o posterior con soporte para venv.

```sh
cd /ruta/a/P_REA/q_Inv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py --create-user admin
.venv/bin/python server.py
```

Abre http://127.0.0.1:8080. No hay credenciales predeterminadas. Para crear más cuentas, repite `--create-user` con otro nombre. En esta etapa todas las cuentas tienen acceso completo al inventario; los roles y restricciones de visibilidad aún están pendientes.

Para probar la importación sin datos reales, ejecuta `.venv/bin/python tools/create_sample.py` e importa el archivo `examples/RVTools-demo.xlsx` generado. Repetir la carga actualiza los mismos tres servidores.

Por defecto los datos se guardan en `data/inventory.sqlite3`. `QINV_DATA` permite seleccionar otro directorio persistente. El servidor escucha únicamente en loopback. Para desplegarlo en la VM utiliza un proxy inverso con HTTPS y ejecuta el proceso mediante systemd como usuario sin privilegios; configura `QINV_SECURE_COOKIE=1` al usar HTTPS. Este servidor de primera etapa requiere endurecimiento operativo antes de exposición a usuarios: límites de intentos de autenticación en el proxy, límites de solicitudes, backups y supervisión del proceso.

Para respaldar una instancia activa usa la API de backup de SQLite o detén el servicio antes de copiar la base; no copies únicamente el archivo `.sqlite3` mientras hay escrituras porque utiliza WAL.

## Conexión SSH, credenciales y recolección

En **Agregar servidor** o **Editar → Conexión SSH y monitoreo**, introduce IP, puerto (22 por defecto), usuario y contraseña. Usa **Conectar y descubrir** para verificar la huella SSH y completar el inventario. Al pulsar **Guardar servidor**, se guardan los datos y la credencial cifrada. La casilla **Recopilar métricas automáticamente** permite activar o pausar las consultas.

Al editar una conexión ya guardada, la contraseña no se devuelve al navegador. Déjala vacía para conservarla o escribe una nueva para reemplazarla. Cambiar de usuario exige introducir contraseña. El descubrimiento puede utilizar la credencial guardada solo con la misma IP, puerto y usuario. No se usa sudo ni se instalan programas en el servidor consultado.

Las contraseñas de la versión anterior eran transitorias: hay que introducirlas una vez para habilitar esta nueva modalidad. El inventario existente se conserva.

### Cifrado y clave maestra

- La contraseña SSH se almacena como un token Fernet (cifrado autenticado), separado de los metadatos de conexión. No se registra la contraseña en claro, no se envía en las respuestas API y no se muestra al editar.
- `QINV_KEY_FILE` indica la ubicación de la clave. En desarrollo se crea `secrets/credentials.key` con permisos 600; el directorio está excluido de Git. Si existen credenciales y falta la clave, el arranque falla en lugar de generar una clave incompatible.
- En instalaciones administradas la clave se encuentra en `/etc/q-inv/credentials.key`, propiedad de root y con permisos 600. systemd 247+ la entrega al servicio mediante `LoadCredential`; la aplicación la lee desde `/run/credentials/`. En systemd anterior el instalador utiliza un archivo de lectura exclusiva para el usuario del servicio, protegido por los permisos de `/etc/q-inv` y la unidad systemd.
- El respaldo de SQLite no incluye la clave. Deben respaldarse ambos por separado para poder restaurar las conexiones. No se debe reemplazar la clave sin migrar antes las contraseñas cifradas.
- La confianza SSH se conserva en `data/ssh_known_hosts`. La primera conexión requiere verificar la huella; un cambio posterior de clave se rechaza y requiere revisión del administrador.

### Métricas y dashboard

El proceso de la aplicación ejecuta un recolector con hasta seis consultas simultáneas, independiente del navegador. El intervalo global es de 5 minutos y la retención de 60 días, ambos editables en Configuración. Las consultas fallidas también quedan registradas. El historial vencido se limpia aproximadamente cada hora. Una solicitud manual en la tarjeta adelanta la siguiente consulta; **Actualizar vista** solo vuelve a leer los datos guardados.

La vista se actualiza cada 20 segundos mientras permanece visible, con búsqueda, filtros de estado y páginas de 12 tarjetas. Muestra estados **Conectado**, **Error SSH**, **Datos antiguos**, **Pendiente**, **Sin configurar** y **Pausado**. Un error SSH no demuestra que el equipo esté apagado. Si una muestra supera el doble del intervalo configurado (mínimo 2 minutos), se marca como antigua.

Para Linux se consultan CPU (muestra de aproximadamente 1 segundo), memoria disponible, uso y capacidad del sistema de archivos raíz `/`, uptime, carga, un sensor térmico si existe, tráfico de interfaces excepto loopback y E/S de discos base visibles. Red y E/S muestran tasas en bytes por segundo y contadores acumulados del sistema. Interfaces virtuales o capas de almacenamiento pueden afectar la interpretación de los contadores. Los datos no disponibles se muestran con un guion, sin inventar ceros.

El descubrimiento de inventario incluye consultas para Linux, AIX y SunOS. Linux intenta leer UUID y detectar virtualización cuando los permisos lo permiten. Grupo, aplicación, host VMware y clúster siguen siendo manuales o procedentes de RVTools. La capacidad descubierta mediante `lsblk` puede incluir varios discos; es diferente del uso de `/` mostrado en el dashboard.

La recolección periódica está implementada inicialmente para Linux. Las consultas de descubrimiento AIX/SunOS se verifican con datos sintéticos; la validación en RHEL 5/6/7/8, AIX 7 y SunOS 11 sigue pendiente. Windows requiere su recolector específico. Los servidores antiguos pueden requerir ajustes de compatibilidad SSH.

## Generar una muestra anonimizada de RVTools

Ejecuta el comando en tu propio equipo, con la ruta al archivo original:

```sh
.venv/bin/python server.py --anonymize "/ruta/RVTools-original.xlsx" "/ruta/RVTools-muestra.xlsx"
```

El comando crea un libro nuevo con hasta 100 registros y solo una hoja `vInfo`. Reemplaza nombres, UUID, IP, hosts y clústeres; utiliza SO, capacidades y estado sintéticos. No copia otras columnas, hojas, fórmulas ni metadatos del libro original. No modifica el original ni sobrescribe un destino existente. Revisa la copia en Excel o LibreOffice antes de compartirla. Si el formato no se reconoce, el comando informa el error y será necesario ajustar el lector.

La muestra sirve para verificar encabezados y el flujo de carga; al sustituir valores no permite comprobar los casos particulares de tus sistemas operativos o capacidades originales. El archivo original puede permanecer en tu equipo.

## Verificación

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

Las pruebas generan archivos sintéticos y utilizan una base temporal. No requieren tus datos reales.

## Próximas etapas

- Roles y grupos de usuarios con restricciones de visibilidad aplicadas desde el backend.
- Integración futura con Active Directory.
- Recolectores adicionales y recepción de datos de scripts; definir el transporte de Windows (PowerShell/WinRM o envío de datos).
- Compatibilidad de recolectores con RHEL 5/6/7/8, AIX 7, SunOS 11 y Windows. El descubrimiento puntual ya dispone de consultas Unix; falta validar cada plataforma y construir monitoreo periódico.
- Consulta gráfica del historial, disponibilidad histórica y personalización de widgets.
- Modelo de reglas y eventos para integrar alertas posteriormente.

Referencias de producto indicadas: NeoServer, Zabbix y Datadog. La interfaz prioriza inventario y carga de datos, con navegación sencilla y diseño adaptable.

## Control de versiones

Cada cambio se registra con Git. El repositorio excluye claves, bases de datos, archivos RVTools, entornos virtuales, respaldos y resultados locales de validación. Las credenciales incluidas en los tests son sintéticas y solo sirven para instancias temporales.

Flujo habitual, desde este directorio:

```sh
git status
git diff
git add archivo_modificado.py
git commit -m "Describe el cambio realizado"
git push
```

Antes de cada commit, revisa `git diff --cached`. GitHub Actions ejecuta las pruebas automatizadas y verifica la sintaxis JavaScript en cada actualización de `main` y en los pull requests. Subir código a GitHub no despliega cambios automáticamente en Zorin; la instancia se actualiza de forma independiente.

El historial comienza con el estado actual del proyecto. Los cambios anteriores a la incorporación de Git no tienen commits individuales.
