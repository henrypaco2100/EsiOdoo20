from odoo import api, models
from odoo.fields import Domain


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_id.invoice_policy', 'company_id.sale_invoice_policy',
                 'order_id.esi_sale_type_id', 'order_id.esi_sale_type_id.invoice_basis')
    def _compute_invoice_policy(self):
        super()._compute_invoice_policy()
        for line in self:
            if line.order_id.esi_sale_type_id:
                line.invoice_policy = line.order_id.esi_sale_type_id.invoice_basis

    def _search_invoice_policy(self, operator, value):
        return (
            (Domain('order_id.esi_sale_type_id', '!=', False)
             & Domain('order_id.esi_sale_type_id.invoice_basis', operator, value))
            | (Domain('order_id.esi_sale_type_id', '=', False)
               & super()._search_invoice_policy(operator, value))
        )

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state',
                 'order_id.invoice_overages', 'order_id.esi_sale_type_id',
                 'order_id.esi_sale_type_id.invoice_basis')
    def _compute_qty_to_invoice(self):
        super()._compute_qty_to_invoice()
