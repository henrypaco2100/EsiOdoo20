from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FinancialFlow(models.Model):
    _name='esi.finance.flow'
    _description='Cuenta de flujo financiero'
    _order='sequence,code,name,id'
    name=fields.Char(required=True,string='Nombre')
    code=fields.Char(string='Código')
    sequence=fields.Integer(default=10,string='Orden')
    active=fields.Boolean(default=True)
    company_id=fields.Many2one('res.company',default=lambda self:self.env.company,string='Compañía')
    parent_id=fields.Many2one('esi.finance.flow',ondelete='restrict',string='Categoría superior')
    child_ids=fields.One2many('esi.finance.flow','parent_id',string='Subcategorías')
    flow_type=fields.Selection([('income','Ingreso'),('expense','Egreso')],default='expense',required=True,string='Tipo')
    note=fields.Text(string='Notas')

    @api.constrains('parent_id','company_id')
    def _validate_parent(self):
        for flow in self:
            parent=flow.parent_id;seen={flow.id}
            while parent:
                if parent.id in seen:raise ValidationError(_('La jerarquía de flujo no puede contener ciclos.'))
                if parent.company_id and parent.company_id!=flow.company_id:raise ValidationError(_('La categoría superior pertenece a otra compañía.'))
                seen.add(parent.id);parent=parent.parent_id


class FlowMoveLine(models.Model):
    _inherit='account.move.line'
    esi_financial_flow_id=fields.Many2one('esi.finance.flow',string='Cuenta de flujo',check_company=True)


class FinancialFlowMove(models.Model):
    _inherit='account.move'

    def _post(self,soft=True):
        # Preserve the Odoo 13 convenience, limited to classification metadata.
        # Amounts, dates, accounts and valuation are never changed here.
        for move in self:
            flows=move.line_ids.filtered(lambda line:line.esi_financial_flow_id and line.account_id.account_type!='asset_cash').esi_financial_flow_id
            if len(flows)==1:
                liquidity=move.line_ids.filtered(lambda line:line.account_id.account_type=='asset_cash' and not line.esi_financial_flow_id)
                if liquidity:liquidity.write({'esi_financial_flow_id':flows.id})
        return super()._post(soft=soft)
