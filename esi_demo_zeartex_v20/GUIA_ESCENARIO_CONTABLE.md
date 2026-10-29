# Zeartex – contabilidad ficticia (Odoo 20 Community)

## Uso recomendado
1. Utilizar exclusivamente una **copia aislada de la base de pruebas**. Hacer respaldo.
2. Instalar/actualizar `esi_demo_zeartex_v20` sin desinstalar el catálogo anterior.
3. Entrar en **ESI Demo Zeartex > Cargar demostración** y confirmar compañía de prueba.
4. Haber cargado el catálogo Zeartex y verificar diarios, cuentas de tercero, cuentas de costo comercial e ingresos.
5. Marcar la casilla de autorización y ejecutar **7. Publicar escenario CONTABLE de prueba** una sola vez.
6. Abrir informes `esi_finanzas_v20` y consultar **01/10/2026 al 28/10/2026**, con **Solo asientos publicados** marcado.

## Resumen de asientos ficticios
- Capital depositado: Bs 250.000.
- Gastos administrativos pagados: Bs 12.000.
- Gastos logísticos no capitalizados: Bs 5.500.
- Factura proveedor de mercadería **sin recepción de stock**: Bs 42.000, costo comercial simulado.
- Factura servicios comerciales: Bs 9.000.
- Factura mayorista: Bs 90.000.
- Factura minorista: Bs 30.000.
- Sin impuestos: todas las líneas de factura se crean sin impuestos para evitar simular obligaciones fiscales reales.
- Resultados de la **simulación sin IVA**: ingresos Bs 120.000, gastos/costos Bs 68.500, resultado Bs 51.500 (si no hay otras operaciones de la compañía).
- Activos simulados: caja/banco Bs 232.500 y CxC Bs 120.000; pasivos CxP Bs 51.000, patrimonio aportado Bs 250.000, resultado Bs 51.500 (sin otras operaciones).

## Importante: compras y ventas futuras
- Un **pedido de compra o venta confirmado** por sí solo NO genera automáticamente una factura publicada ni todos los asientos financieros.
- Para compras normales: orden de compra > recepción según corresponda > **factura del proveedor** > **publicar** > pago.
- Para ventas normales: orden de venta/POS > entrega según corresponda > **factura** > **publicar** > cobro.
- Inventario AVCO y costos en destino son independientes de este escenario contable ficticio. No registrar por duplicado compras o gastos en un segundo asiento cuando se validen los procesos reales.
- Para obtener estados financieros que reflejen inventario y costo de ventas reales, se necesitarán movimientos físicos y valoración contable coherente; los registros de prueba publicados aquí solo sirven para visualizar los informes.

## Seguridad
La carga es idempotente por referencia `ZEA-CONT-DEMO-2026`; si ya existe un documento con esa referencia en la compañía, no ejecuta otra vez. Requiere autorización explícita. La transacción se revierte en caso de error.
