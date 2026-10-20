from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    esi_group_id = fields.Many2one('esi.production.group', string='Grupo de fabricación', index=True, copy=False)
    esi_responsible_id = fields.Many2one('res.users', string='Responsable de fabricación', tracking=True)
    esi_analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
        help='Referencia analítica operativa. No se inyecta en la valoración de inventario.',
    )
    esi_note = fields.Text(string='Notas')

    def action_esi_destajo(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': 'Registrar destajo',
                'res_model': 'esi.destajo', 'view_mode': 'form', 'target': 'current',
                'context': dict(self.env.context, default_production_id=self.id,
                    default_analytic_account_id=self.esi_analytic_account_id.id)}

    def _get_backorder_mo_vals(self):
        values = super()._get_backorder_mo_vals()
        values['esi_group_id'] = self.esi_group_id.id or False
        return values
