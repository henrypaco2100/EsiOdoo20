from odoo import api, SUPERUSER_ID
from odoo.addons.esi_calzados_v20.hooks import mark_existing_components


def migrate(cr, version):
    mark_existing_components(api.Environment(cr, SUPERUSER_ID, {}))
