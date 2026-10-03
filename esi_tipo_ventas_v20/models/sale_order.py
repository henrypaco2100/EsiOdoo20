from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    esi_sale_type_id = fields.Many2one(
        'esi.sale.type', string='Tipo de Venta ESI',
        domain="[('company_id', '=', company_id)]",
        copy=True,
        help='Clasificación comercial. No modifica warehouse_id, rutas, entregas, facturación ni pedidos web.',
    )
