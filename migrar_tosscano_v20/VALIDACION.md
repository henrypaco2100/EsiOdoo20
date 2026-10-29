# Validación de la versión 20.0.5.0.0

51 pruebas locales aprobadas. Incluyen conservación de cantidades, costos por sucursal, identidad de productos, saldos repetidos, categorías, lógica contable aislada y botón de recetas. Se comprueba que las LdM creadas pertenecen a Fábrica, que repetir no duplica y que unidades incompatibles o recetas vacías no crean LdM parciales.

Python y XML analizados; archivos del manifiesto presentes; ZIP comprobado. Las pruebas de métodos usan dobles ORM. No se probó instalación en un servidor Odoo ni el resultado contable real.

Pendiente de datos: equivalencias indicadas en INCIDENCIAS_RECETAS.md y saldo negativo TEX-PEK-18-EST (−18 m). Las doce fichas no producirán LdM completas con las correspondencias actuales.
