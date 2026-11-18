from odoo import api, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received',
                 'product_uom_qty', 'product_qty', 'order_id.state', 'order_id.esi_purchase_type_id',
                 'order_id.esi_purchase_type_id.invoice_basis')
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        for line in self:
            config = line.order_id.esi_purchase_type_id
            if (line.order_id.state == 'purchase' and not line.display_type
                    and not line.is_downpayment and config):
                quantity = line.product_qty if config.invoice_basis == 'ordered' else line.qty_received
                line.qty_to_invoice = quantity - line.qty_invoiced
