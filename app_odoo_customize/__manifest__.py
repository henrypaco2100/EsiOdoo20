{
 'name': 'ESI - Limpieza avanzada de base de pruebas',
 'version': '20.0.3.1.0',
 'category': 'Administration',
 'summary': 'Limpieza selectiva y reinicio de datos de pruebas por sucursal',
 'author': 'ESI', 'license': 'LGPL-3',
 'depends': ['base_setup', 'web', 'esi_sucursales_v20'],
 'data': ['security/ir.access.csv', 'views/cleanup_views.xml'],
 'installable': True, 'application': False, 'auto_install': False,
}
