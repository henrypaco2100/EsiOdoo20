{
 'name': 'Migración Tosscano v20',
 'version': '20.0.6.8.0',
 'summary': 'Carga directa de categorías, unidades, productos, cuentas y saldos',
 'author': 'ESI', 'license': 'LGPL-3', 'application': True,
 'depends': ['sale_product_matrix', 'esi_calzados_v20', 'esi_sucursales_v20', 'account', 'stock', 'stock_account', 'sale', 'purchase'],
 'data': ['security/ir.access.csv', 'views/migration.xml', 'views/recipe_real.xml', 'views/size_tags.xml'],
 'assets': {'web.assets_backend': ['migrar_tosscano_v20/static/src/size_tags.js']},
 'installable': True,
}
