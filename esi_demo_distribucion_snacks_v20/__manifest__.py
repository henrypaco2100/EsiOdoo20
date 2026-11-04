{
    "name": "ESI - Distribución de Snacks",
    "version": "20.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Visitas a clientes, pedidos y notas de venta para distribuidores",
    "author": "ESI - Especialistas en Sistemas Integrados",
    "license": "LGPL-3",
    "depends": ["sale", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/visit_views.xml",
        "views/demo_wizard_views.xml",
        "report/visit_report.xml",
    ],
    "installable": True,
    "application": True,
}
