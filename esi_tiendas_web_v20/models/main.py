from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Website(models.Model):
    _inherit = 'website'
    esi_store_id = fields.Many2one('esi.store', string='Sucursal comercial web', check_company=True)
    def _prepare_sale_order_values(self, partner_sudo):
        vals = super()._prepare_sale_order_values(partner_sudo)
        vals['esi_store_id'] = self.esi_store_id.id
        return vals

class Sale(models.Model):
    _inherit = 'sale.order'
    def _is_cart_ready_for_payment(self):
        ready = super()._is_cart_ready_for_payment()
        if self.website_id and not (self.esi_store_id or self.warehouse_id.esi_store_id or self.website_id.esi_store_id):
            self._add_blocking_alert(_('Este pedido necesita asignación de sucursal. Contacte al vendedor antes de pagar.'))
            return False
        return ready
    def action_confirm(self):
        for order in self.filtered('website_id'):
            if order.carrier_id.delivery_type == 'in_store':
                order.esi_store_id = order.warehouse_id.esi_store_id
            if not order.esi_store_id:
                order.esi_store_id = order.warehouse_id.esi_store_id or order.website_id.esi_store_id
            if not order.esi_store_id:
                raise UserError(_('Asigne una sucursal al pedido web o a su almacén antes de confirmar.'))
        return super().action_confirm()
