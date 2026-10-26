# ESI | DEMO IMPORTADORA ZEARTEX SRL — Odoo 20 Community

## Instalación
1. RESPALDE su base y pruebe primero en una base de pruebas.
2. Extraiga `esi_demo_zeartex_v20/` en la carpeta de addons de Odoo 20.
3. Reinicie Odoo, actualice la lista de aplicaciones e instale «ESI | Demo Importadora Zeartex SRL».
4. Entre a **ESI Demo Zeartex > Cargar demostración**, seleccione la compañía en BOB y use los botones numerados.

## Botones disponibles
1. **Cargar catálogo**: genera 150 plantillas, variantes, 8 proveedores, 25 clientes, dos listas de precios y fotografías integradas. Solo administra registros DEMO.
2. **Crear borradores**: solicita cotizaciones de compra y venta de ejemplo. No las confirma.
3. **Configurar POS**: crea la tienda Zeartex, únicamente si hay un método de pago ya configurado para la compañía. Abrir caja se hace manualmente.
4. **Cargar stock**: ejecuta un ajuste de inventario verdadero para las variantes, SOLO tras confirmación, y solo si los productos no tienen cantidad previa en ese almacén. Afecta la valoración contable, use exclusivamente en una base de pruebas.

## Alcance y precauciones
- Las 6 fotos de catálogo son imágenes de apariencia fotográfica generadas para la DEMO; cada familia tiene una fotografía representativa, no hay 150 fotografías individuales ni se presentan como imágenes oficiales de fabricantes.
- Precios y proveedores son ficticios. Los 150 productos base producen más de 150 variantes.
- El coste de proveedores se guarda en BOB por seguridad. Compras extranjeras en USD, ajustes aduaneros y costos en destino se deben completar según configuración de la compañía. No se afirma tener automatización aduanera.
- Facturación electrónica SIN no incluida. No se crean facturas contables automáticamente.
- El POS es una tienda independiente, pero productos disponibles en POS pueden ser visibles desde otros puntos de venta si estos no filtran categorías.
- No se cambian impuestos, cuentas, diarios, tipos de cambio ni moneda de la compañía.
- Se exige compañía BOB para las listas de precio.
- **PRUEBAS:** estructura, imágenes, integridad de JSON, sintaxis Python y XML verificadas. No se ha realizado prueba de instalación en una instancia Odoo 20 ejecutándose.
