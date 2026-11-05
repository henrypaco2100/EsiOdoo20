# ESI Agrocons – actualización de informes financieros (20.0.3.10.0)

## Alcance
- Se incluye EXCLUSIVAMENTE `esi_demo_agrocons_v20`. No sustituye ni modifica `esi_finanzas_v20` o `esi_reportes_base_v20`.
- Extiende por herencia el modelo `esi.finance.report` y su formulario original de Facturación → Reportes.
- Para compañías que tienen asientos Agrocons publicados (referencias `AGC-CONT-DEMO-2026` o `AGC-AMPLIACION-2026-`), el botón **Consultar** muestra grupos y totales de Balance/Resultados; Libro Mayor detallado y Sumas y Saldos con saldos iniciales.
- El mismo conjunto de datos es empleado por Consultar, PDF y Excel de ESI. Los otros informes conservan su lógica existente.

## Filtros
- Compañía y sucursales, fecha desde/hasta, publicados, analítica, cuentas y contacto: de ESI Finanzas.
- Nuevos: diarios, mostrar cuentas con movimientos / con saldo / todas, incluir saldo inicial en Mayor, orden de Mayor.
- Con los otros filtros vacíos se consideran todos los registros aplicables.
- Balance: corte a la fecha final, incluye saldos previos; Resultados: exclusivamente el período elegido.

## Crear un escenario financiero adicional (OPCIONAL)
- En una **COPIA AISLADA** de la base, abra Gestión Agrícola → Configuración → Cargar DEMO Agrocons.
- Seleccione compañía y marque las dos autorizaciones.
- Ejecute `Cargar movimientos financieros ampliados` para crear 17 cuentas si faltan y 14 asientos equilibrados de ejemplo de banco, capital, crédito, maquinaria, vehículo, herramientas, combustible, labores, servicios, transporte y depreciación.
- Solo se publica UNA VEZ por compañía. No se crean movimientos de inventario, stock ni valoración. Los asientos son datos demostrativos independientes: NO representan compra/venta real de existencias y NO se deben mezclar con contabilidad operativa.
- Los asientos que se publiquen en compras/ventas reales de Odoo también aparecerán, dentro del rango y compañía del informe.

## IMPORTANTE: Odoo 20 y valoración de stock
- La recepción física se refleja en Inventario, la factura publicada en Contabilidad. Confirmar un pedido no equivale a publicar factura.
- En valoración *periódica al cierre*, el asiento para conciliar existencias con valoración contable ocurre durante el cierre, NO al confirmar cada movimiento.
- AVCO es un método de costeo distinto del momento de la valoración contable. El código no modifica AVCO ni altera `esi_finanzas_v20`.

## Verificación necesaria en un Odoo 20 real
1. Respaldo de la base y actualizar únicamente `esi_demo_agrocons_v20`.
2. Abrir Facturación → Reportes → Balance General. Consultar compañía y mes con movimientos publicados.
3. Comprobar que Total Activo = Total Pasivo + Patrimonio (diferencia 0.00) y que Sumas y Saldos tiene Débito = Crédito.
4. Abrir Libro Mayor y contrastar movimientos con `account.move.line`, PDF y Excel.
5. Crear factura real de prueba en Compras y otra en Ventas, publicarlas y comprobar que los importes aparecen con la fecha y compañía correctas.
6. Validar procesos de stock/valoración y costeo agrícola aparte; este paquete no certifica conciliación física-contable.

## Límites
- No se ha ejecutado una instalación real en el servidor Odoo 20. Las pruebas incluidas son estáticas.
- El escenario de apertura financiera del asistente es ficticio, no generador de existencias físicas.
- Los filtros contables no garantizan rentabilidad positiva; muestran los saldos reales de los asientos consultados.
