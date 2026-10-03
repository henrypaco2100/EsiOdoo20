from odoo import fields, models
class Config(models.Model):
    _inherit = 'pos.config'
    esi_store_id = fields.Many2one('esi.store', string='Sucursal comercial ESI', check_company=True)
class Order(models.Model):
    _inherit = 'pos.order'
    esi_store_id = fields.Many2one(related='config_id.esi_store_id', string='Sucursal ESI', store=True)
    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        vals['esi_store_id'] = self.esi_store_id.id
        return vals
