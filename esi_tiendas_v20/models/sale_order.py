from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    esi_store_id = fields.Many2one(
        'esi.store', check_company=True, string='Tienda / Sucursal',
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self.env.user.esi_store_id if self.env.user.esi_store_id.company_id == self.env.company else False,
        copy=True,
        help='Dimensión comercial y analítica. No cambia el almacén ni las rutas del pedido.',
    )

    @api.onchange('esi_store_id')
    def _onchange_esi_store_id(self):
        for order in self:
            order._esi_apply_store_analytic(only_empty=True)

    def _esi_apply_store_analytic(self, only_empty=True):
        for order in self:
            account = order.esi_store_id.analytic_account_id
            if not account:
                continue
            distribution = {str(account.id): 100.0}
            for line in order.order_line.filtered(lambda l: not l.display_type):
                if only_empty and line.analytic_distribution:
                    continue
                line.analytic_distribution = distribution
        return True

    def action_esi_apply_store_analytic(self):
        self._esi_apply_store_analytic(only_empty=False)
        return True

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.esi_store_id:
            vals['esi_store_id'] = self.esi_store_id.id
        return vals
