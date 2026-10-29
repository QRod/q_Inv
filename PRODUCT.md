# q_Inv

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Equipos de infraestructura que administran inventarios de servidores físicos y virtuales y necesitan consultar sus recursos, clasificación y estado de conexión.

## Product Purpose

Centralizar inventario, clasificación y métricas de servidores mediante importación RVTools, alta manual y conexión SSH.

## Operating Context

Aplicación web autohospedada en Linux con systemd y Python 3.11+. Acceso mediante HTTPS y cuentas locales con autorizaciones por grupos. Recolección inicial cada cinco minutos y retención de sesenta días, ambas configurables.

## Capabilities and Constraints

- Inventario manual y conciliación de vInfo/vNetwork de RVTools por UUID, con tarjetas e IPs IPv4/IPv6.
- Grupos y aplicaciones múltiples, ambiente, responsable principal y etiquetas.
- Descubrimiento SSH para Linux, AIX y SunOS; métricas periódicas disponibles para Linux. La compatibilidad debe validarse por plataforma y versión.
- Credenciales SSH cifradas y comprobación de huellas; algoritmos de conexión modernos.
- Vista previa y confirmación de importaciones y operaciones masivas.
- Roles Administrador, Operador y Lector con control de acceso en el backend.
- Servidores sin grupo exclusivos de administradores; cambios de cuenta revocan sesiones.
- Ficha de servidor con estado, inventario y gráficas de recursos históricos; rangos, promedios, máximos y periodos sin datos explícitos.
- Auditoría de acciones y resultados, sin secretos, exclusiva de administradores.
- Consulta manual de versiones con comandos de respaldo y actualización; la instalación se realiza desde el sistema operativo.
- Active Directory, alertas, widgets personalizables y recolector Windows no están integrados.

## Brand Commitments

Nombre q_Inv, interfaz en español y presentación centrada en el inventario y la lectura de recursos. Superficies neutras, jerarquía clara, cifras legibles y un botón para alternar entre temas claro y oscuro.

## Evidence on Hand

Documentación funcional, pruebas de backend y recorridos de navegador con datos sintéticos. Las capturas públicas muestran exclusivamente ejemplos y no representan infraestructura real. No se publican testimonios, certificaciones ni garantías de rendimiento.

## Product Principles

1. Distinguir capacidad inventariada de consumo medido y ausencia de datos de cero.
2. Explicar efectos y confirmar operaciones destructivas o masivas.
3. Mantener navegación por teclado y estados comprensibles; el color acompaña texto.
4. Conservar tareas y contexto ante actualizaciones o fallos de conexión.
