from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EsiStore(models.Model):
    _name = 'esi.store'
    _description = 'Tienda / Sucursal'
    _order = 'sequence, name'

    name = fields.Char(string='Tienda / Sucursal', required=True)
    code = fields.Char(string='Código', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company, index=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
        help='Dimensión financiera de la tienda. No controla inventario ni rutas.',
    )
    warehouse_ids = fields.One2many('stock.warehouse', 'esi_store_id', string='Almacenes relacionados')
    user_ids = fields.Many2many('res.users', 'esi_store_user_rel', 'store_id', 'user_id', string='Usuarios')
    note = fields.Text(string='Notas')

    _esi_store_code_company_uniq = models.Constraint('unique(code, company_id)', 'El código de la tienda debe ser único por compañía.')

    @api.constrains('analytic_account_id', 'company_id')
    def _check_analytic_company(self):
        for rec in self:
            if rec.analytic_account_id.company_id and rec.analytic_account_id.company_id != rec.company_id:
                raise ValidationError(_('La cuenta analítica debe pertenecer a la misma compañía de la tienda.'))
