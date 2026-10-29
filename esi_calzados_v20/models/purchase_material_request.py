from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Odoo normally requires a vendor even for drafts. Only manufacturing
    # material requests may omit it; keep that restriction server-side too.
    partner_id = fields.Many2one(required=False)
    esi_material_request = fields.Boolean(string='Solicitud de materiales de fabricación',
                                        readonly=True, copy=True, default=False)

    @api.constrains('partner_id', 'esi_material_request', 'state')
    def _esi_check_request_vendor(self):
        for order in self:
            if not order.partner_id and not (order.esi_material_request and order.state in ('draft', 'cancel')):
                raise ValidationError(_('Seleccione un proveedor. Solo las solicitudes de materiales de fabricación en borrador pueden quedar sin proveedor.'))

    @api.model_create_multi
    def create(self, values_list):
        orders = super().create(values_list)
        # Also validate when partner_id is absent from the incoming values.
        orders._esi_check_request_vendor()
        return orders

    def _esi_require_vendor(self):
        if self.filtered(lambda order: not order.partner_id):
            raise UserError(_('Asigne un proveedor antes de enviar o confirmar la solicitud. Puede guardarla sin proveedor mientras esté en borrador.'))

    def button_confirm(self):
        self._esi_require_vendor()
        return super().button_confirm()

    def button_approve(self, force=False):
        self._esi_require_vendor()
        return super().button_approve(force=force)

    def action_rfq_send(self):
        self._esi_require_vendor()
        return super().action_rfq_send()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _get_seller_info(self):
        self.ensure_one()
        if self.order_id.esi_material_request and not self.order_id.partner_id:
            # Do not pick an arbitrary seller's quotation when no vendor was
            # selected. Native pricing falls back to the product's cost.
            return {}
        return super()._get_seller_info()
