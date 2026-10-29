from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EsiDestajo(models.Model):
    _name = 'esi.destajo'
    _description = 'Destajo de Producción'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(default='Nuevo', readonly=True, copy=False)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    production_id = fields.Many2one('mrp.production', string='Orden de producción', required=True, ondelete='cascade', index=True)
    group_id = fields.Many2one(related='production_id.esi_group_id', string='Grupo', store=True)
    operator_id = fields.Many2one('res.partner', string='Operador', required=True, tracking=True)
    activity = fields.Char(string='Actividad', required=True)
    quantity = fields.Float(string='Cantidad', default=1.0, required=True)
    unit_price = fields.Monetary(string='Tarifa', required=True)
    amount_total = fields.Monetary(string='Total', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, readonly=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
        help='Solo clasificación del destajo. No se modifica la valoración de materiales/producto terminado.',
    )
    note = fields.Text()

    @api.depends('quantity','unit_price')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = rec.quantity * rec.unit_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('esi.destajo') or 'Nuevo'
        return super().create(vals_list)

    @api.constrains('quantity', 'unit_price', 'analytic_account_id', 'production_id')
    def _check_amounts_company(self):
        for rec in self:
            if rec.quantity <= 0 or rec.unit_price < 0:
                raise ValidationError(_('La cantidad debe ser positiva y la tarifa no puede ser negativa.'))
            if rec.analytic_account_id.company_id and rec.analytic_account_id.company_id != rec.company_id:
                raise ValidationError(_('La cuenta analítica pertenece a otra compañía.'))
