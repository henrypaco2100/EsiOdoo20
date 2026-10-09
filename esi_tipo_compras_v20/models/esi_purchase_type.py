from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EsiPurchaseType(models.Model):
    _name = 'esi.purchase.type'
    _inherit = 'esi.branch.mixin'
    _description = 'Tipo de Compra'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(string='Código', index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    note = fields.Text(string='Descripción')

    _esi_purchase_type_name_company_uniq = models.Constraint('unique(name, company_id)', 'El tipo de compra debe ser único por compañía.')

    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén predeterminado', check_company=True, domain="[('company_id', '=', company_id)]")
    journal_id = fields.Many2one('account.journal', string='Diario de facturación', check_company=True, domain="[('company_id', '=', company_id), ('type', '=', 'purchase')]")
    validation_picking = fields.Boolean(string='Validar recepción preparada', default=False, help='Solo valida operaciones ya marcadas como realizadas. No rellena cantidades ni omite asistentes de lotes o entregas parciales.')
    create_invoice = fields.Boolean(string='Crear factura al confirmar', default=False)
    validate_invoice = fields.Boolean(string='Publicar facturas borrador', default=False)
    allow_payment = fields.Boolean(string='Permitir Registrar pago desde el pedido', default=True)

    @api.constrains('company_id', 'warehouse_id', 'journal_id')
    def _check_configuration(self):
        for rec in self:
            if rec.warehouse_id and rec.warehouse_id.company_id != rec.company_id:
                raise ValidationError(_('El almacén debe pertenecer a la misma sucursal.'))
            if rec.journal_id and (rec.journal_id.company_id != rec.company_id or rec.journal_id.type != 'purchase'):
                raise ValidationError(_('El diario debe ser del tipo correcto y de la misma sucursal.'))

    @api.onchange('company_id')
    def _onchange_company(self):
        self.warehouse_id = False
        self.journal_id = False
