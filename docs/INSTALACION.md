# Instalación en Linux

El instalador independiente descarga una entrega de GitHub Releases, verifica SHA-256, instala dependencias y crea servicios de aplicación y HTTPS. Requiere Linux con systemd, acceso root y Python 3.11+ disponible en los repositorios de la distribución. Código en `/opt/q-inv/releases/`, enlace `current`, datos en `/var/lib/q-inv` y configuración privada en `/etc/q-inv`.

Para una IP o nombre de la red local, sustituye `SERVIDOR`:

```sh
curl -fsSL https://raw.githubusercontent.com/QRod/q_Inv/v0.8.0/install.sh -o install.sh
less install.sh
sudo bash install.sh --version v0.8.0 --address SERVIDOR --https-port 8443
```

La CA local genera el certificado en cada instalación; no hay certificados ni claves compartidos. El navegador advertirá de la falta de confianza hasta importar la CA local del proxy en el cliente.

Para dominio y certificado público de Let's Encrypt:

```sh
sudo bash install.sh --version v0.8.0 --address app.example.com --tls public --https-port 443 --email admin@example.com
```

El DNS debe apuntar al servidor y los puertos 80/443 estar libres y accesibles desde Internet. Caddy gestiona emisión y renovación. Si ya tienes un proxy compartido o esos puertos ocupados, usa `--proxy external` y configura tu proxy HTTPS contra el backend en loopback; el instalador no modifica ese proxy. El firewall permanece bajo administración del operador.

Después de instalar, crea la primera cuenta de forma interactiva:

```sh
sudo q-inv-admin --create-user admin
```

El comando detiene brevemente la app, solicita la contraseña sin mostrarla, conserva la propiedad de los datos y vuelve a iniciar el servicio.

### Distribuciones y límites

Se prepararon rutas para Debian/Ubuntu/Zorin/Mint (`apt`), Fedora/RHEL/Rocky/AlmaLinux (`dnf`), openSUSE (`zypper`) y Arch/Manjaro (`pacman`). El proxy incluido tiene binarios oficiales verificados para x86_64 y ARM64. No implica compatibilidad con todas las versiones históricas: se exige Python 3.11+, venv y systemd. En Arch se presupone un sistema actualizado; el instalador no hace una actualización global. Alpine/OpenRC y NixOS requieren instalación manual.

La instalación real se valida en Zorin OS. La detección de las otras familias se prueba con archivos os-release; aún no se ha ejecutado la instalación completa en ellas. La configuración de TLS público está preparada, pero su emisión real requiere un dominio y DNS del operador.

### Actualización, respaldo y recuperación

Vuelve a ejecutar el instalador indicando la nueva etiqueta con las mismas opciones (las preferencias de instalación quedan guardadas de forma privada). No se descarga una rama de desarrollo como si fuera una entrega. Cada versión tiene su propio entorno virtual. Antes del cambio se respalda SQLite mediante su API, junto con configuración y unidades anteriores en `/var/backups/q-inv`.

Si el nuevo servicio falla en la comprobación de arranque, el instalador intenta restaurar la versión, base y configuración anteriores. La recuperación manual debe hacerse con el servicio detenido y utilizando el respaldo de la misma fecha; volver solo al código no revierte una migración de datos. Conserva además copias externas de datos y claves; el instalador no sustituye una política de respaldo.

Para migrar una instalación manual, añade `--migrate-from /ruta/a/la/instalacion`. Se copia la base sin borrar el origen. Para q_Inv con credenciales ya cifradas, coloca antes su clave original en `/etc/q-inv/credentials.key` con permisos 600: una clave diferente no recupera las contraseñas anteriores.

La consulta de versiones y el respaldo administrativo se describen en [Acceso y operación](ACCESO-Y-OPERACION.md).
