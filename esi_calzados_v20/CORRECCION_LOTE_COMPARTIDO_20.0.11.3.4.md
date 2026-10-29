# Corrección 20.0.11.3.4 — lote común por OF multitalle

- El lote indicado una sola vez en la Orden de Fabricación se propaga a todas las tallas de salida.
- Odoo conserva un `stock.lot` separado por producto/variante, usando el mismo nombre de lote para toda la OF.
- Los lotes creados automáticamente reciben como referencia interna el nombre de la OF.
- No se sobrescriben lotes distintos ingresados manualmente.
- Si un producto terminado está configurado **Por número de serie**, se informa que el flujo multitalle compartido requiere **Por lotes**.

Ejemplo:

- OF: `FABRICA/MO/00015`
- Lote ingresado: `FABRICA/MO/00015`
- T38 -> lote `FABRICA/MO/00015`
- T39 -> lote `FABRICA/MO/00015`
- T40 -> lote `FABRICA/MO/00015`

Internamente son tres registros `stock.lot` (uno por producto), todos con el mismo nombre de lote y trazabilidad hacia la misma OF.
