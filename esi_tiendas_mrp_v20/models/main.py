from odoo import fields, models
class Production(models.Model):
    _inherit = 'mrp.production'
    esi_store_id = fields.Many2one(related='picking_type_id.warehouse_id.esi_store_id', string='Sucursal de fabricación', store=True)
