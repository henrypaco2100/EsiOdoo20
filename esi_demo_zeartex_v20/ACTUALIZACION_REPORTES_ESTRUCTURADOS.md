# Informes financieros estructurados — Zeartex

Esta versión añade a ESI Demo Zeartex dos accesos nuevos: **Balance General estructurado** y **Estado de Resultados estructurado**. No modifica los registros contables ya publicados ni sustituye los informes ESI existentes.

- El Balance usa todos los saldos publicados hasta la fecha de corte; separa activo corriente, no corriente, pasivo corriente, no corriente y patrimonio, e incorpora los resultados aún sin cierre.
- El Estado de Resultados muestra ingresos, costo de ventas, utilidad bruta, gastos y resultado del período.
- Se generan subtotales con los importes reales presentes en `account.move.line`; no se inventan cuentas ni cifras. Para otros informes ESI continúan funcionando Sumas y Saldos, Mayor, Caja/Bancos y CxC/CxP.
- El título aclara que los importes proceden de registros; no oculta las referencias históricas de los asientos.
- Para una demostración con cuentas inventariables y compras/ventas reales, se deben validar recepciones, entregas, facturas y costos en destino a través de Odoo y conciliar el libro de inventario con contabilidad; este módulo **no** crea movimientos de almacén por sí mismo al instalarse.
- No se borran ni reescriben etiquetas existentes de facturas publicadas. Si una factura anterior dice «DEMO» o «ficticia», se conserva para no alterar el historial auditado. Las futuras operaciones reales se registran con nombres normales de productos, desde Compras y Ventas.

## Instalación

Extraer `esi_demo_zeartex_v20` en addons y actualizar en Aplicaciones. Requiere `esi_finanzas_v20` y sus dependencias ya disponibles. Reiniciar Odoo para cargar los nuevos modelos. Abrir ESI Demo Zeartex → Balance General estructurado / Estado de Resultados estructurado. Verificar compañía, fecha y «Solo asientos publicados». Usar Consultar/PDF/Excel.

## Limitaciones

Verificada la sintaxis de Python y la estructura de XML, pero no se ejecutó instalación ni cálculo real en un servidor Odoo 20; probar en base aislada antes de presentarlo. No utilizar como estados financieros oficiales sin revisión contable y fiscal.
