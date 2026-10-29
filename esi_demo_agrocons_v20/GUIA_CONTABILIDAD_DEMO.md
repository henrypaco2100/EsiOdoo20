# Escenario contable de prueba – Familia Agrocons

## Seguridad
Acción **Publicar escenario contable DEMO** exclusivamente en una **copia aislada de la base** (no en producción). Publica cinco documentos ficticios en la compañía elegida. No crea movimientos de almacén ni capas de valoración y **no representa el costo inventariable real de la cosecha**.

## Orden de uso
1. Hacer backup y restaurar base de pruebas aislada.
2. Cargar datos Agrocons.
3. Verificar AVCO.
4. Verificar diario general, ventas y compras, cuentas bancarias, de capital, ingresos y gastos.
5. Marcar las dos confirmaciones y ejecutar **Publicar escenario contable DEMO** una sola vez.
6. En `Facturación > Reportes` abrir Balance, Resultados, Sumas y saldos, Libro mayor, Caja y bancos, CxC y CxP; período 01/10/2026 al 28/10/2026; compañía elegida; `Solo asientos publicados` activado.

## Movimientos ficticios (en moneda principal de la compañía)
- Capital: 250.000, caja/banco contra patrimonio.
- Gastos operativos pagados: 13.500.
- Factura proveedor insumos, publicada, 40.000. Representa gasto de demostración, **no recepción física**.
- Factura servicios agrícolas, publicada, 22.000.
- Factura venta soya, publicada, 185.000. **No equivale a entrega física ni movimiento de stock**.

**Importante**: esta simulación contable permite obtener saldos financieros y ver la mecánica de CxC/CxP. Para mostrar inventario real de soya, costo promedio AVCO, costo de ventas y margen auditado deben validarse separadamente recepciones, consumos y cosechas. No debe representarse esta simulación como contabilidad real de una campaña terminada.

La acción comprueba que no haya ejecutado antes el mismo escenario para evitar duplicaciones. Un fallo durante la publicación revierte la transacción de Odoo. La configuración fiscal y cuentas deben revisarse antes de publicar documentos de prueba.
