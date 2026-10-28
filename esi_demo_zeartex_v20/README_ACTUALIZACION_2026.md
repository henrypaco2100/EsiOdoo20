# ESI Demo Zeartex v20 – Actualización 20.0.2.0.0

Esta entrega reemplaza la carpeta de la versión instalada `esi_demo_zeartex_v20`. No se debe instalar una segunda copia con otro nombre.

## Funciones
- Conserva los 150 productos, fotografías ilustrativas, variantes, clientes, proveedores y POS existentes.
- Añade cuatro expedientes de importación ficticios: marítimo, aéreo, terrestre y ferroviario.
- Genera servicios de costos en destino para los gastos capitalizables; el IVA recuperable ilustrativo aparece SEPARADO y no se incorpora al costo.
- Crea órdenes de compra DEMO en borrador para cada escenario si ya existe catálogo y proveedor.
- Permite preparar borradores **reales de stock.landed.cost** solo después de seleccionar recepciones ya validadas.
- No valida automáticamente entradas de stock, asientos, facturas ni costos en destino.
- Configura AVCO solamente en categorías exclusivamente Zeartex sin existencias y sin movimientos confirmados; muestra categorías bloqueadas sin forzar cambios.

## Secuencia segura
1. Hacer copia de seguridad de una base de prueba, NO usar en base operativa.
2. Reemplazar carpeta del addon y actualizar módulo.
3. Menú ESI Demo Zeartex > Cargar demostración: cargar catálogo (si faltara).
4. Pulsar «5. Configurar AVCO seguro» ANTES de generar movimientos de inventario. Si informa categorías bloqueadas, NO forzar: revisar migración de valoración individual.
5. Pulsar «6. Crear 4 importaciones de ejemplo».
6. Abrir Importaciones y costos, ajustar importes y tipo de cambio ilustrativo.
7. Para materializar una importación: confirmar una compra y validar su recepción **manualmente en base de pruebas**; vincular esa recepción con el expediente, y pulsar «Preparar costo en destino Odoo».
8. Revisar los productos de gasto, cuentas contables, distribución y el tipo de cambio; calcular los ajustes y validar el costo **manualmente** en el formulario estándar de Odoo SOLO si procede.

## Limitaciones explícitas
- Los importes de arancel e IVA son supuestos y NO tienen validez tributaria. Las posiciones arancelarias requieren clasificación real.
- Las estimaciones de compras y gastos en USD no sustituyen la tasa de cambio legal vigente. Para generar costo en destino, se usa la tasa *manual de simulación* del expediente en BOB.
- Las cuatro importaciones no generan automáticamente facturas, diarios, balances ni asientos publicados. Los reportes `esi_finanzas_v20` pueden seguir usándose por separado si ya están instalados.
- No se fuerza el cambio de valoración periódica a perpetua ni se modifica el plan de cuentas.
- No hay posibilidad de prueba de instalación contra la base real en este entorno; las pruebas realizadas son estáticas y de integridad.
