# Contabilidad continua - Odoo 20 Community (ESI)

Esta actualización NO agrega asientos automáticos adicionales: evita duplicar los que genera Odoo.

## Flujo de compras
1. Crear y confirmar orden de compra en Compras.
2. Recibir productos en Inventario: actualiza stock y costo AVCO según configuración.
3. Crear factura de proveedor desde la orden o Facturación.
4. Comprobar impuestos, cuentas, diarios y fechas; **PUBLICAR** la factura para generar asientos contables.
5. Registrar el pago y conciliar si corresponde.

## Flujo de ventas
1. Crear y confirmar pedido en Ventas (o vender en POS, cerrando la sesión según configuración).
2. Entregar mercancía en Inventario.
3. Crear y PUBLICAR factura de cliente; se generan apuntes de ingresos y cuenta por cobrar.
4. Registrar cobro y conciliar.

## AVCO e inventario
AVCO calcula el costo de inventario, pero NO es sinónimo de contabilización automática de todos los movimientos.
Si la compañía usa valoración PERIODIC (at closing), debe ejecutar el cierre de inventario para llevar la valoración a la contabilidad. No forzar asientos duplicados por código.
Los costos en destino deben validarse contra recepciones reales, sin duplicar el IVA recuperable.

## Menús nuevos
- Asientos de operaciones (todos): muestra cualquier asiento PUBLICADO autorizado al usuario, no solo los de una referencia fija de la demo.
- Facturas de ventas y Facturas de compras: incluyen borradores y publicadas para detectar por qué faltan movimientos.
- Verificar diarios y asientos: diagnostica diarios, cuentas básicas y cantidad de movimientos de la compañía.

## Seguridad
Realizar las pruebas en una base aislada. La instalación no publica asientos, factura ni modifica saldos por sí sola. El filtrado multicompañía respeta las reglas del usuario en la lista general.
