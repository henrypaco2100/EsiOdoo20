{
    'name': 'Kardex por talla',
    'version': '20.0.1.3.1', 'author': 'ESI', 'license': 'LGPL-3',
    'depends': ['stock', 'esi_calzados_v20', 'esi_reportes_base_v20'],
    'assets': {'web.assets_backend': ['esi_inventario_calzados_v20/static/src/report.scss']},
    'data': ['security/ir.access.csv', 'views/report.xml', 'report/document.xml'],
    'installable': True, 'application': False,
}
