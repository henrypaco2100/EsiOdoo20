{'name': 'Kardex físico por almacén',
 'version': '20.0.3.0.0',
 'author': 'ESI',
 'maintainer': 'ESI',
 'license': 'LGPL-3',
 'category': 'Inventory/Reporting',
 'summary': 'Consulta de movimientos y saldos por almacén, producto y unidad; '
            'sin alterar valoración',
 'depends': ['stock', 'web', 'esi_sucursales_v20'],
 'external_dependencies': {'python': ['xlsxwriter']},
 'data': ['security/ir.access.csv', 'views/kardex.xml', 'report/kardex.xml'],
 'application': False,
 'installable': True}
