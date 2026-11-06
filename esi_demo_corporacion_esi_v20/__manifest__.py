{
    'name': 'ESI | Demo Corporacion ESI - Multisucursal Agro',
    'version': '20.0.1.0.0',
    'category': 'Industries/Agriculture',
    'summary': 'Demo multisucursal con plan contable compartido, AVCO, valoracion automatica, productos y saldos fuente',
    'author': 'ESI - Especialistas en Sistemas Integrados',
    'maintainer': 'ESI',
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'depends': [
        'base', 'product', 'stock', 'stock_account', 'purchase', 'sale_management', 'account',
        'esi_sucursales_v20', 'esi_tipo_ventas_v20', 'esi_tipo_compras_v20',
        'esi_reportes_base_v20', 'esi_finanzas_v20', 'esi_kardex_v20',
        'esi_ventas_report_v20', 'esi_compras_report_v20',
    ],
    'data': [
        'security/ir.access.csv',
        'views/demo_wizard_views.xml',
    ],
}
