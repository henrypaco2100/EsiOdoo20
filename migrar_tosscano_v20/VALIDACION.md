# Validación de la versión 20.0.6.0.0

63 pruebas locales aprobadas. Incluyen conservación de cantidades, costos por sucursal, identidad de productos, saldos repetidos, categorías, lógica contable aislada y botón de recetas. Se comprueba que las LdM creadas pertenecen a Fábrica, que repetir no duplica y que unidades incompatibles o recetas vacías no crean LdM parciales.

Python y XML analizados; archivos del manifiesto presentes; ZIP comprobado. Las pruebas de métodos usan dobles ORM. No se probó instalación en un servidor Odoo ni el resultado contable real.

Pendiente de datos: equivalencias indicadas en INCIDENCIAS_RECETAS.md y saldo negativo TEX-PEK-18-EST (−18 m). Las doce fichas no producirán LdM completas con las correspondencias actuales.

La política de tallas completa 58 plantillas no infantiles a 34–46; ocho escolares mantienen sus tallas. Se verificó que los datos de saldos coinciden íntegramente con la versión 20.0.5.0.0.

Precios: coincidencias delimitadas y específicas, tratamiento de mayorista vacío, detección de importes inválidos, cobertura de 65 plantillas, importación de reglas nativas por plantilla y repetición sin duplicar ni sobrescribir precios ya procesados. Las pruebas ORM usan dobles; no se ejecutó instalación real de Odoo.
