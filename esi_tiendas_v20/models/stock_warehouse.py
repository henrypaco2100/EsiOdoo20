from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    esi_store_id = fields.Many2one(
        'esi.store', check_company=True, string='Tienda relacionada',
        domain="[('company_id', '=', company_id)]",
        help='Relación informativa. No modifica rutas, reglas de reabastecimiento, ubicaciones ni movimientos.',
    )
