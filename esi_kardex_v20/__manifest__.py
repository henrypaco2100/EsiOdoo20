{'name': 'Kardex físico y valorado por almacén',
 'version': '20.0.4.1.0',
 'author': 'ESI',
 'maintainer': 'ESI',
 'license': 'LGPL-3',
 'category': 'Inventory/Reporting',
 'summary': 'Consulta de movimientos y saldos por almacén, producto y unidad; '
            'sin alterar valoración',
 'depends': ['esi_reportes_base_v20', 'stock', 'stock_account', 'web', 'esi_sucursales_v20'],
 'external_dependencies': {'python': ['xlsxwriter']},
 'assets': {'web.assets_backend': ['esi_kardex_v20/static/src/report.scss']},
 'data': ['security/ir.access.csv', 'views/kardex.xml', 'report/kardex.xml'],
 'application': False,
 'installable': True}
