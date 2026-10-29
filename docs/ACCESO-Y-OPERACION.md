# Acceso, auditoría y actualizaciones

## Roles y grupos

| Operación | Administrador | Operador | Lector |
|---|---|---|---|
| Consultar inventario y métricas | Todos | Sus grupos | Sus grupos |
| Alta y edición de servidores | Sí | Dentro de sus grupos | No |
| Descubrimiento y consulta SSH | Sí | Servidores guardados de sus grupos | No |
| Organización masiva | Sí | Selección íntegra dentro de su ámbito | No |
| Eliminar servidores | Sí, con confirmación | No | No |
| Importar RVTools | Sí | No | No |
| Administrar catálogos, usuarios y autorizaciones | Sí | No | No |
| Configuración global, auditoría y actualizaciones | Sí | No | No |

Un equipo es visible si pertenece al menos a un grupo autorizado de la cuenta.
Un equipo sin grupo solo es visible para administradores. Las cuentas restringidas
solo reciben servidores, recuentos y opciones de clasificación de su ámbito.
Los grupos asignados, aunque estén vacíos, aparecen como opciones de alta.
Los equipos compartidos pueden mostrar sus otras pertenencias como metadatos;
eso no autoriza a consultar los demás equipos de esos grupos.

Un operador puede mantener o cambiar sus pertenencias autorizadas, pero no añadir
ni retirar grupos ajenos ni dejar el equipo fuera de su ámbito. Para cambiar la IP,
el puerto o el usuario SSH de un equipo con credenciales guardadas, debe introducir
una contraseña para el nuevo destino; no se reutiliza de forma implícita un secreto
guardado contra otro destino. El descubrimiento de un equipo nuevo requiere
guardarlo primero dentro de un grupo autorizado. Los lectores no reciben usuario
ni puerto de las credenciales SSH.

## Cuentas locales

Desde **Usuarios y permisos**, una cuenta administradora crea usuarios, asigna rol
y grupos, restablece contraseñas o desactiva cuentas. No se eliminan cuentas para
conservar sus referencias históricas. Las contraseñas nuevas tienen de 12 a 1024
caracteres y se guardan mediante scrypt, nunca en texto plano.

Cambiar una cuenta revoca sus sesiones existentes, incluidas las propias. Las
solicitudes de escritura vuelven a comprobar identidad y autorizaciones dentro de
la transacción. Las operaciones masivas también vuelven a verificar su selección
al confirmar. No se puede desactivar ni degradar al último administrador activo.

En la migración de una instalación anterior, **todas las cuentas existentes se
conservan como administradoras**, manteniendo identificadores y contraseñas.
Revisar esos roles antes de incorporar nuevos usuarios. Las cuentas nuevas creadas
por consola son lectoras por defecto, excepto la primera cuenta, que debe ser
administradora. Se puede elegir explícitamente:

```sh
sudo q-inv-admin --create-user admin
sudo q-inv-admin --create-user operador --role operator
```

La cuenta creada por consola sin grupos no ve equipos hasta que un administrador
le asigne autorizaciones desde la interfaz. Active Directory no está integrado en
esta entrega; las autorizaciones son independientes del método futuro de identidad.

## Auditoría

La sección **Auditoría**, exclusiva de administradores, permite filtrar por acción
y resultado, paginar y consultar detalles. Incluye accesos, cambios de usuarios,
servidores, clasificación, catálogos, importaciones, eliminaciones, configuración,
consultas de métricas, comprobaciones de actualizaciones e intentos denegados.
Las lecturas normales de inventario no producen un evento por cada consulta.

Las mutaciones y sus eventos se confirman en la misma transacción. Se guardan
usuario, fecha UTC, acción, resultado y entidades afectadas; cuando corresponde,
estado anterior y posterior. La interfaz presenta la fecha en la zona horaria del
navegador. Los cambios de contraseña se indican con un booleano; no se registran
contraseñas, cifrados de credenciales, hashes de acceso, tokens ni claves.

Los registros anteriores se conservan como eventos `legacy`. Los detalles grandes
pueden resumirse, con marca `truncated` y sus identificadores, para limitar tamaño.
La API no permite modificar ni borrar eventos y SQLite bloquea UPDATE/DELETE en
la tabla de auditoría. Esto **no protege frente a alguien con control del archivo
de base de datos o del sistema operativo**. Para conservación independiente,
inmutabilidad externa y políticas regulatorias se requiere otra etapa de operación.

## Buscar actualizaciones

En **Configuración → Actualizaciones de q_Inv → Buscar actualizaciones**:

1. Se consulta la última publicación estable del repositorio oficial.
2. Se compara su versión `vMAJOR.MINOR.PATCH` con el archivo VERSION instalado.
3. Se muestran enlace y comandos, solo si hay una versión posterior disponible.
4. Un administrador del sistema revisa y ejecuta esos comandos en el servidor.

La consulta es manual: no hay sondeo automático ni instalación desde HTTP. No se
envían inventario, nombres de equipos ni credenciales a GitHub. Usa un destino HTTPS
fijo, rechaza redirecciones y limita tiempo y tamaño de respuesta. Requiere conexión
a la API pública de GitHub; un error de red o límite de consultas se muestra y se
puede reintentar. Los comandos corresponden a instalaciones mediante install.sh.
Un checkout de desarrollo no sustituye el flujo de instalación del servidor.

Para impedir las consultas en un entorno sin salida a Internet, usar un override
de systemd que persiste al reinstalar la unidad:

```sh
sudo systemctl edit q-inv
```

```ini
[Service]
Environment=QINV_UPDATE_CHECKS=0
```

Después ejecutar `sudo systemctl daemon-reload` y `sudo systemctl restart q-inv`.
El proxy corporativo y sus certificados se configuran por administración del
servidor; no se pueden indicar URLs o ejecutables arbitrarios desde la interfaz.

## Respaldo y actualización manual

Primero, desde una cuenta del sistema con sudo:

```sh
sudo q-inv-admin --backup /var/backups/q-inv/manual-$(date +%Y%m%d-%H%M%S)
```

El wrapper detiene brevemente q_Inv y lo vuelve a iniciar incluso si el comando
falla. Se crea un directorio nuevo de acceso restringido que contiene una copia
consistente de SQLite, la clave de credenciales y los archivos install.env y
runtime.env cuando existen. Conserva también VERSION. Si falla, el directorio se
marca INCOMPLETE; no usarlo para restaurar. No se sobrescriben directorios previos.
La creación del respaldo queda auditada como acción de consola.

La base y la clave deben conservarse juntas y fuera del servidor, con acceso
restringido. Este respaldo de aplicación no incluye los certificados ni la
configuración de un proxy externo ni equivale a una copia completa de la VM.

Después, revisar y ejecutar el instalador de la versión estable que mostró la app.
El instalador verifica el SHA-256 del artefacto y conserva la configuración local;
también genera su propio respaldo previo. La autenticidad depende del repositorio
oficial y del canal HTTPS: no se afirma una verificación de firma independiente.

Para entornos desconectados se puede transferir un artefacto oficial, su instalador
y la suma obtenida por un canal confiable; usar las opciones `--archive`, `--sha256`
y `--version` descritas por `install.sh --help`. Las dependencias de Python y del
sistema también deben estar disponibles: no es un instalador offline completo.

### Restauración

Detener q_Inv y restaurar una base, clave y configuración pertenecientes al mismo
respaldo, con código compatible con su VERSION. Usar la API backup de SQLite o una
copia con todas las conexiones cerradas; no mezclar una base antigua con archivos
WAL/SHM de la instalación actual. Devolver la propiedad del directorio de datos a
la cuenta del servicio, conservar la clave solo para root y reiniciar el servicio.
Probar una restauración en una instancia aislada antes de depender del respaldo.

Para volver a una versión anterior con otras reglas de autorización, restaurar
también su base y configuración previas: **no servir código anterior con la base
actual**, pues podría ignorar los roles nuevos. El instalador revierte automáticamente
su propio corte fallido; una reversión posterior requiere administración del sistema.

## Política SSH y dependencias

Esta entrega utiliza Paramiko 5.1.0 y aborda el aviso
CVE-2026-44405 / PYSEC-2026-2858 de la versión 4. La rama 5 elimina los intercambios
DH y las firmas RSA basados en SHA-1. Los equipos que solo acepten esos mecanismos
no se conectarán; no se habilitan algoritmos antiguos globalmente para sortearlo.

Las conexiones a RHEL 5/6, AIX y SunOS antiguos requieren validación con cada
versión de sistema y configuración SSH. El inventario manual y la importación siguen
disponibles aunque su servidor SSH requiera modernizarse. Esto no afirma compatibilidad de monitoreo con
cada sistema: las métricas periódicas actuales siguen siendo inicialmente Linux.

Fuentes: [notas oficiales de Paramiko](https://www.paramiko.org/changelog.html) y
[aviso revisado](https://github.com/advisories/GHSA-r374-rxx8-8654).
