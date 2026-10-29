# Datos de red en la API

Los objetos de servidor de `GET /api/servers` y `GET /api/dashboard` incorporan:

| Campo | Contenido |
|---|---|
| `ip` | Dirección principal de conexión de q_Inv; conserva el contrato existente. |
| `reported_primary_ip` | Principal reportada en la última importación RVTools, o cadena vacía. |
| `network_interfaces` | Lista de tarjetas importadas; vacía cuando no hay datos guardados. |
| `ip_addresses` | Lista sin duplicados de la principal de q_Inv, principal reportada e IPs de las tarjetas. |

Cada tarjeta tiene `label`, `adapter_type`, `network`, `switch`, `mac_address`, `connected`, `starts_connected`, `ip_addresses` y `source`. Los estados son booleanos o `null` cuando no se conocen. Las IPs y MAC se normalizan; una tarjeta puede no tener IP. `source` identifica `vNetwork` o el resumen `vInfo`.

Estos campos se filtran con los mismos permisos que el servidor. Los datos de red se actualizan desde la importación; `POST /api/servers` mantiene las tarjetas guardadas y no permite modificarlas con campos adicionales del formulario.

La vista previa de importación incorpora `data.network_interfaces` cuando el archivo incluye datos de tarjetas, `connection_ip` para mostrar el destino previsto y `connection_ip_preserved` cuando difiere del principal reportado. Omitir `network_interfaces` conserva lo existente; una lista vacía representa una exportación que no reporta tarjetas para esa VM. Los errores de red incluyen `sheet: "vNetwork"`, `line` y `error`.

La confirmación sigue comprobando token, usuario y expiración y consume la vista previa una sola vez. Guardar inventario, red y auditoría forma parte de la misma transacción. Una confirmación ya consumida no se puede repetir. Las vistas previas de eliminación detectan también cambios en las tarjetas antes de borrar.
