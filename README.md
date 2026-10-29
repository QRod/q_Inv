# q_Inv

**Inventario y monitoreo de servidores físicos y virtuales.**

q_Inv centraliza el inventario de infraestructura, organiza los equipos por servicio y aplicación, y permite consultar sus recursos desde una interfaz web. Combina importación de RVTools, registro manual, monitoreo SSH y control de acceso por grupos.

[![Verificación](https://github.com/QRod/q_Inv/actions/workflows/tests.yml/badge.svg)](https://github.com/QRod/q_Inv/actions/workflows/tests.yml)

[Descargar](https://github.com/QRod/q_Inv/releases/latest) · [Instalación](docs/INSTALACION.md) · [Guía de uso](docs/GUIA-DE-USO.md) · [Cambios](CHANGELOG.md) · [Licencia MIT](LICENSE)

![Dashboard de q_Inv en tema claro con doce servidores de demostración, estados de conexión e indicadores de recursos.](docs/images/dashboard-claro.png)

*Todas las capturas utilizan una instancia temporal con datos ficticios. Los nombres, direcciones IP, cuentas y métricas son ejemplos; no representan infraestructura real.*

## Funcionalidades

- **Inventario centralizado.** Registro y edición de servidores físicos y virtuales, con IP, sistema operativo, UUID, CPU, RAM, disco, host y clúster.
- **Importación RVTools.** Archivos Excel con hoja `vInfo`, validación, vista previa y conciliación por UUID para actualizar registros sin duplicarlos.
- **Organización flexible.** Varios grupos y aplicaciones por servidor, ambiente, responsable principal y etiquetas; búsqueda, filtros y clasificación masiva.
- **Dashboard de recursos.** Tarjetas compactas con CPU, memoria, disco raíz, red y E/S, estados de conexión y detalles ampliables.
- **Monitoreo SSH.** Descubrimiento de inventario y recolección periódica Linux, con credenciales cifradas, comprobación de huella y retención configurable.
- **Usuarios y permisos.** Cuentas locales con roles Administrador, Operador y Lector, y visibilidad por grupos de servidores.
- **Auditoría.** Consulta de acciones, resultados y cambios anteriores/posteriores, sin incluir contraseñas.
- **Operación administrada.** Consulta manual de actualizaciones, comandos de respaldo y actualización, instalación Linux con systemd y HTTPS.
- **Interfaz adaptable.** Temas Claro, Oscuro y Sistema, navegación por teclado y vistas adaptadas a dispositivos móviles.

## Pantallas

### Inventario

Consulta capacidades y clasificaciones, filtra equipos y realiza operaciones sobre la selección.

![Inventario con servidores ficticios, capacidades de CPU, RAM y disco, grupos, aplicaciones y acciones de edición.](docs/images/inventario.png)

<details>
<summary><strong>Importación RVTools y organización</strong></summary>

La importación presenta los registros nuevos y las actualizaciones antes de confirmar. La conciliación conserva la clasificación existente.

![Vista previa de una importación RVTools con tres servidores ficticios y sus capacidades.](docs/images/importacion-rvtools.png)

Los catálogos comparten grupos, aplicaciones, ambientes, responsables y etiquetas entre servidores. Renombrar una entrada conserva sus asignaciones.

![Catálogo de grupos de ejemplo con descripciones, recuentos de servidores y acciones de administración.](docs/images/organizacion.png)

</details>

<details>
<summary><strong>Usuarios, permisos y auditoría</strong></summary>

Asigna roles y grupos a cada cuenta. Los operadores modifican equipos de sus grupos; los lectores solo consultan. Los servidores sin grupo son exclusivos de administradores.

![Administración de tres cuentas ficticias con roles Administrador, Operador y Lector y sus grupos autorizados.](docs/images/usuarios-permisos.png)

Revisa acciones y resultados con filtros y detalles de los cambios registrados.

![Auditoría de acciones realizadas sobre datos de demostración con fecha, cuenta, acción y resultado.](docs/images/auditoria.png)

</details>

<details>
<summary><strong>Tema oscuro</strong></summary>

La apariencia puede seleccionarse manualmente o seguir la configuración del sistema.

![Dashboard de los mismos doce servidores de demostración en tema oscuro.](docs/images/dashboard-oscuro.png)

</details>

## Instalación rápida

Requiere una VM o servidor Linux con **systemd**, acceso administrativo y **Python 3.11 o posterior** disponible en los repositorios de la distribución.

Descarga y revisa el instalador de la versión estable; sustituye `SERVIDOR` por la IP o el nombre del servidor:

```sh
curl -fsSL https://raw.githubusercontent.com/QRod/q_Inv/v0.5.0/install.sh -o q-inv-install.sh
less q-inv-install.sh
sudo bash q-inv-install.sh --version v0.5.0 --address SERVIDOR --https-port 8443
```

Crea la primera cuenta administradora:

```sh
sudo q-inv-admin --create-user admin
```

Accede a `https://SERVIDOR:8443`. La opción HTTPS local requiere confiar en la CA generada por la instalación. También se admite certificado público con dominio o un proxy inverso existente.

El instalador verifica el SHA-256 de la entrega, crea un servicio sin privilegios y separa código, datos y configuración. Consulta la [guía de instalación](docs/INSTALACION.md) para las familias Linux, HTTPS, migración y recuperación.

## Compatibilidad y alcance

| Área | Alcance actual |
|---|---|
| Instalación | Linux con systemd y Python 3.11+. Rutas para familias Debian/Ubuntu, Fedora/RHEL, openSUSE y Arch. |
| Inventario | Alta manual de servidores físicos y virtuales; importación de `vInfo` de RVTools. |
| Monitoreo periódico | Linux mediante SSH con algoritmos modernos. Intervalo inicial de 5 minutos y retención de 60 días, configurables. |
| Otros sistemas | Consultas de descubrimiento para AIX y SunOS pendientes de validación por plataforma; Windows admite inventario manual/importado, sin recolector específico. |
| Identidad | Usuarios locales. Active Directory no está integrado. |
| Actualizaciones | Consulta de publicaciones estables y guía de comandos; instalación ejecutada por el administrador del sistema. |

Las capacidades de inventario se distinguen del consumo medido. El disco del dashboard corresponde al sistema de archivos raíz `/`; un error SSH no demuestra que el servidor esté apagado. La compatibilidad de sistemas antiguos debe verificarse por versión; no se habilitan algoritmos SHA-1. Los widgets personalizables, las gráficas de historial y las alertas no están disponibles en la versión actual.

## Documentación

- [Guía de uso](docs/GUIA-DE-USO.md): dashboard, inventario, clasificación, RVTools y conexión SSH.
- [Instalación](docs/INSTALACION.md): requisitos, distribuciones, HTTPS y despliegue.
- [Acceso y operación](docs/ACCESO-Y-OPERACION.md): permisos, auditoría, respaldo, restauración y actualizaciones.
- [Desarrollo](docs/DESARROLLO.md): ejecución desde código, pruebas y empaquetado.
- [Historial de cambios](CHANGELOG.md) y [publicaciones](https://github.com/QRod/q_Inv/releases).

## Licencia

q_Inv se distribuye bajo la [licencia MIT](LICENSE). Las dependencias conservan sus licencias correspondientes.
