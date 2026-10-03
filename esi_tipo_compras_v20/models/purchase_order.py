from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    esi_purchase_type_id = fields.Many2one(
        'esi.purchase.type', string='Tipo de Compra ESI',
        domain="[('company_id', '=', company_id)]",
        copy=True,
        help='Clasificación de compra. No modifica picking_type_id, recepción, rutas ni reabastecimiento.',
    )
