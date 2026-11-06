from odoo import fields, models


class FinancialOrder(models.Model):
    _name = 'esi.finance.classic.order'
    _description = 'Orden de cuentas en estados financieros'
    _order = 'kind, sequence, id'
    _rec_name = 'account_id'

    sequence = fields.Integer(default=10, string='Orden')
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company,
        string='Matriz / compañía', help='Esta configuración se aplica también a las sucursales descendientes autorizadas.')
    kind = fields.Selection([('balance','Balance general'),('profit','Estado de resultados')], required=True, default='balance', string='Estado financiero')
    account_id = fields.Many2one('account.account', required=True, string='Cuenta o título del plan',
        context={'active_test':False}, ondelete='cascade')
    label = fields.Char(string='Título en el reporte', help='Opcional: cambia únicamente la presentación del informe.')
    _unique_order = models.Constraint('UNIQUE(company_id, kind, account_id)', 'La cuenta ya tiene un orden configurado en este informe y compañía.')
