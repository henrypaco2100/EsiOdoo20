{
 'name': 'Migración Tosscano v20',
 'version': '20.0.7.1.0',
 'summary': 'Carga directa de categorías, unidades, productos, cuentas y saldos',
 'author': 'ESI', 'license': 'LGPL-3', 'application': True,
 'depends': ['esi_calzados_v20', 'esi_sucursales_v20', 'account', 'stock', 'stock_account', 'sale', 'purchase'],
 'data': ['security/ir.access.csv', 'views/migration.xml'],
 'installable': True,
}
