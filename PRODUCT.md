# q_Inv

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Personal del área de infraestructura de una empresa con alrededor de 500 equipos
físicos y virtuales. Administra el inventario y consulta el estado de sus servidores.

## Product Purpose

Centralizar inventario, clasificación y métricas de servidores, con importación
desde RVTools y alta manual o asistida mediante SSH.

## Operating Context

Desarrollo en P_REA; repositorio de la aplicación independiente. Despliegue en una
VM Linux. Usuarios locales inicialmente; Active Directory es una integración futura.
Frecuencia base de recolección de cinco minutos y retención de sesenta días,
ambas configurables. Las alertas se integrarán posteriormente.

## Capabilities and Constraints

- Inventario manual y conciliación RVTools por UUID.
- Grupos y aplicaciones múltiples, ambiente y responsable principal, etiquetas.
- Descubrimiento SSH para Linux, AIX y SunOS; métricas periódicas actuales para Linux.
- Credenciales SSH cifradas; contraseñas guardadas no se muestran en formularios.
- Previsualización y confirmación antes de importaciones y operaciones masivas.
- El error SSH no demuestra que un equipo esté apagado.
- No alterar datos del servidor desplegado durante pruebas de diseño.
- Mantener HTML/CSS/JavaScript y backend Python existentes.
- Administrador con acceso completo; operador modifica sus grupos y lector solo consulta.
- Servidores sin grupo exclusivos de administradores; las cuentas anteriores migran
  como administradoras para preservar acceso. Los cambios de cuenta revocan sesiones.
- Auditoría de cambios sin secretos, visible para administradores.
- Consultar publicaciones estables desde la app y guiar el respaldo/actualización por
  un administrador del sistema. No instalar ni ejecutar comandos desde la web.

## Brand Commitments

Nombre q_Inv, interfaz en español y prioridad de una UI limpia, sencilla y funcional.
El usuario eligió referencias Braun/Nothing y tema claro/oscuro con selector, y
autorizó implementar correcciones, rediseño y despliegue en el servidor de pruebas.
La interpretación de «Braum» como Braun se comunicó al usuario; no se inventan
otras preferencias de marca.

## Evidence on Hand

Revisión de diseño y funcionalidad en `docs/reviews/2026-10-28-diseno-funcionalidad.md`.
Fixtures sintéticos, pruebas de backend y recorridos de navegador existentes.
Referencia inicial de widgets de NeoServer compartida por el usuario: conservar
CPU, RAM, disco, red y E/S disponibles. No existen testimonios ni cifras comerciales.

## Product Principles

1. Distinguir capacidad de inventario de recursos medidos y ausencia de datos de cero.
2. Explicar efectos y confirmar operaciones destructivas o masivas.
3. Priorizar lectura, navegación por teclado y estados comprensibles.
4. Conservar tareas y contexto ante actualizaciones o fallos de conexión.

## Política de conexión confirmada

El usuario eligió Paramiko 5.1 y algoritmos SSH modernos, con validación de los
sistemas antiguos durante el piloto. No reintroducir algoritmos obsoletos para
recuperar compatibilidad sin una nueva decisión explícita.
