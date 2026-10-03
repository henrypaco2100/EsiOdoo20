from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    esi_store_id = fields.Many2one(
        'esi.store', check_company=True, string='Tienda / Sucursal ESI',
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self.env.user.esi_store_id if self.env.user.esi_store_id.company_id == self.env.company else False,
        copy=True,
        help='Dimensión financiera. No modifica la valoración de existencias ni los asientos automáticos de stock.',
    )

    @api.onchange('esi_store_id')
    def _onchange_esi_store_id(self):
        for move in self:
            move._esi_apply_store_analytic(only_empty=True)

    def _esi_apply_store_analytic(self, only_empty=True):
        for move in self:
            account = move.esi_store_id.analytic_account_id
            if not account:
                continue
            distribution = {str(account.id): 100.0}
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note')):
                if only_empty and line.analytic_distribution:
                    continue
                line.analytic_distribution = distribution
        return True

    def action_esi_apply_store_analytic(self):
        self._esi_apply_store_analytic(only_empty=False)
        return True
