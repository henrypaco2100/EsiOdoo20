from odoo import fields, models


class EsiPurchaseType(models.Model):
    _name = 'esi.purchase.type'
    _description = 'Tipo de Compra ESI'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(string='Código', index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    note = fields.Text(string='Descripción')

    _esi_purchase_type_name_company_uniq = models.Constraint('unique(name, company_id)', 'El tipo de compra debe ser único por compañía.')
