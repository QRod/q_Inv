# Cambios

## v0.6.0 — 2026-10-29

- Importación de todas las tarjetas de `vNetwork`, con red, MAC, tipo de adaptador, switch y estados de conexión.
- Varias direcciones IPv4/IPv6 por tarjeta; compatibilidad con columnas separadas y la columna `IP Address`.
- Conciliación por UUID; un nombre ambiguo bloquea la importación cuando falta ese identificador.
- Vista previa y detalle de red en inventario, edición y dashboard; búsqueda por IP secundaria, red y MAC.
- La importación conserva el destino de conexiones SSH guardadas y registra por separado la IP principal reportada.
- Reimportación de redes sin duplicados; los archivos sin información de tarjetas conservan los datos de red existentes.
- Datos de red incluidos en auditoría y eliminados junto con el registro de inventario.

## v0.5.0 — 2026-10-29

- Roles de administrador, operador y lector; visibilidad y modificación por grupos,
  verificadas en el backend y al confirmar operaciones masivas.
- Gestión de usuarios, permisos y contraseñas; desactivación y revocación de sesiones.
- Protección del último administrador activo y migración de cuentas anteriores
  conservando su acceso administrador.
- Auditoría estructurada, paginada y consultable; cambios antes/después sin secretos.
- Búsqueda manual de actualizaciones estables con guía de comandos; sin ejecución web.
- Respaldo privado y consistente mediante la consola administrativa.
- Paramiko 5.1.0 y negociación SSH moderna; los servidores antiguos requieren validación
  y podrían necesitar actualización de su configuración SSH.

La base agrega roles, autorizaciones y campos de auditoría. Las credenciales,
cuentas, inventario, organización, configuración y métricas se conservan. Ver la guía
[Acceso y operación](docs/ACCESO-Y-OPERACION.md) antes de migrar o restaurar.

## v0.4.1 — 2026-10-28

- Tarjetas del dashboard compactas, de aproximadamente un cuarto del área anterior
  en escritorio, con porcentajes y barras de recursos legibles.
- Red y E/S resumidas; acumulados, metadatos y mensajes completos accesibles en Detalles.
- Hasta 48 servidores por página y conservación de detalles abiertos al refrescar.

## v0.4.0 — 2026-10-28

### Añadido

- Temas Claro, Oscuro y Sistema con selección persistente por navegador.
- Pruebas de temas, adaptación de 320 a 1440 px, navegación por teclado y fallos de actualización.

### Mejorado

- Interfaz coherente de inventario y monitoreo, con superficies neutras y jerarquía visual uniforme.
- Contraste, legibilidad, iconos y tamaño de controles; navegación móvil completa.
- Formulario con registro manual primero y descubrimiento SSH opcional.
- Nombres accesibles de los diálogos y contexto de la navegación principal.

### Corregido

- Pérdida del foco de teclado al refrescar las tarjetas de servidores.
- Mensaje de dashboard vacío cuando solo faltaban coincidencias del filtro.
- Falta de aviso persistente cuando falla la actualización del dashboard.

No hay cambios de esquema ni de contratos de API. Se conservan cuentas, inventario,
organización, credenciales, métricas y preferencias de recolección existentes.
