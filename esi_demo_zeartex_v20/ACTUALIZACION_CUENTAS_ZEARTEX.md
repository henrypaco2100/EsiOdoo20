# Actualización cuentas contables Zeartex 20.0.2.4.0

Corrige el bloqueo «Faltan cuentas contables adecuadas para: Costo comercial».

- El asistente reutiliza cuentas existentes del plan contable de la compañía.
- Si no hay cuenta `expense_direct_cost`, crea una cuenta exclusiva para la compañía seleccionada, entre los códigos 519901 y 519999.
- No crea duplicados al ejecutar varias veces: busca la cuenta antes de crearla.
- El botón «Preparar cuentas contables Zeartex» solamente prepara la cuenta, no genera asientos.
- La publicación del escenario contable la realiza el botón 7 de forma explícita en base aislada de pruebas.
- No sustituye una cuenta de costo comercial por una cuenta administrativa genérica.
- No cambia el método AVCO, categorías de productos, inventario ni reportes de otras empresas.

**Advertencia:** el escenario de asientos ficticios no está enlazado a movimientos físicos ni valoraciones del inventario. No mezclarlo con contabilidad operativa real. Requiere pruebas de instalación y publicación en Odoo 20.
