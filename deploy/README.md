# Despliegue

`install.sh` genera el servicio systemd y la configuración HTTPS. El código se instala en `/opt/q-inv/releases/`, los datos en `/var/lib/q-inv` y la configuración privada en `/etc/q-inv`.

Con un proxy inverso existente, utilizar `--proxy external` y dirigir HTTPS al puerto del backend en loopback. El instalador conserva la administración del proxy externo y del firewall a cargo del operador.

Consultar [Instalación](../docs/INSTALACION.md) y [Acceso y operación](../docs/ACCESO-Y-OPERACION.md) para requisitos, certificados, respaldo, actualización y restauración.
