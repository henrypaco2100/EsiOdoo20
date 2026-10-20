{
    "name": "ESI - Personalización y Limpieza Multisucursal Odoo 20",
    "version": "20.0.1.0.0",
    "category": "Administration",
    "summary": "Herramientas administrativas y limpieza segura por sucursal/compañía",
    "author": "ESI",
    "license": "LGPL-3",
    "depends": ["base_setup", "web", "esi_sucursales_v20"],
    "data": [
        "security/ir.model.access.csv",
        "views/cleanup_wizard_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "app_odoo_customize/static/src/scss/cleanup.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
