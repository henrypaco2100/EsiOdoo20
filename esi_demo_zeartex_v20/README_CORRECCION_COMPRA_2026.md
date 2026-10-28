# Corrección de carga de cuatro importaciones (Odoo 20)

- Version 20.0.2.0.1
- `purchase.order.line.taxes_id` sustituido por `tax_ids`.
- Verificación previa de proveedor, variantes y campo de impuestos para generar un error legible.
- Mantiene costos en destino en borrador; no valida recepciones ni asientos.
- Actualizar el módulo existente; no desinstalar ni borrar registros.
- La validación estática no equivale a prueba real de instalación en Odoo 20.
