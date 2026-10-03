from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    esi_analytic_names = fields.Char(string='Analítica ESI', compute='_compute_esi_analytic_names')

    def _compute_esi_analytic_names(self):
        Analytic = self.env['account.analytic.account']
        for line in self:
            ids = set()
            for key in (line.analytic_distribution or {}).keys():
                for part in str(key).split(','):
                    if part.strip().isdigit():
                        ids.add(int(part.strip()))
            line.esi_analytic_names = ', '.join(Analytic.browse(sorted(ids)).exists().mapped('display_name'))
