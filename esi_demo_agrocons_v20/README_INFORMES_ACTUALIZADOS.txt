FAMILIA AGROCONS / INFORMES FINANCIEROS EN ODOO 20

Este ZIP contiene exclusivamente esi_demo_agrocons_v20.
No modifica ni distribuye esi_finanzas_v20 ni esi_reportes_base_v20.

Cuando la compañía seleccionada tiene el escenario contable Agrocons publicado
(referencias AGC-CONT-DEMO-2026), los menús originales de Facturación > Reportes >
Balance general, Estado de resultados, Sumas y saldos y Libro mayor utilizan
la presentación jerárquica de esta extensión mediante _inherit de esi.finance.report.
También afecta Consultar, PDF y Excel si estos consumen _report_data.
El resto de informes conserva la implementación del módulo ESI original.

Los informes utilizan importes de asientos reales publicados y pueden cambiar
al contabilizar nuevas operaciones. Los asientos de la DEMO inicial son
ficticios; no crean cosechas ni inventario por sí mismos.

La extensión no cambia la contabilidad ni valoración AVCO por sí sola.

Primero instale/actualice en copia aislada de pruebas. Abra un reporte ORIGINAL
de Facturación y pulse Consultar. Verifique el cuadre, PDF y Excel.
La prueba de integración en servidor Odoo 20 debe ejecutarse en su entorno.
