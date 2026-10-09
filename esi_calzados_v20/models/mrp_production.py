from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    esi_group_id = fields.Many2one('esi.production.group', string='Grupo de producción', index=True, copy=False)
    esi_responsible_id = fields.Many2one('res.users', string='Encargado de producción', tracking=True)
    esi_analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
        help='Referencia analítica operativa. No se inyecta en la valoración de inventario.',
    )
    esi_note = fields.Text(string='Notas')
