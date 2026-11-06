from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

ACCOUNT_TYPES = [
 ('asset_receivable','Por cobrar'),('asset_cash','Banco y caja'),('asset_current','Activo corriente'),
 ('asset_non_current','Activo no corriente'),('asset_prepayments','Anticipos'),('asset_fixed','Activo fijo'),
 ('liability_payable','Por pagar'),('liability_credit_card','Tarjeta de crédito'),('liability_current','Pasivo corriente'),
 ('liability_non_current','Pasivo no corriente'),('equity','Patrimonio'),('equity_unaffected','Resultado del ejercicio'),
 ('income','Ingresos'),('income_other','Otros ingresos'),('expense','Gastos'),
 ('expense_other','Otros gastos'),('expense_depreciation','Depreciación'),('expense_direct_cost','Costos directos'),('off_balance','Fuera de balance')]


class FinancialType(models.Model):
    _name = 'esi.finance.account.type'
    _description = 'Tipo contable para estructuras financieras'
    name = fields.Char(required=True)
    code = fields.Selection(ACCOUNT_TYPES, required=True)
    _unique_code = models.Constraint('UNIQUE(code)', 'El tipo contable ya existe.')


class FinancialLayout(models.Model):
    _name = 'esi.finance.layout'
    _description = 'Estructura de estado financiero'
    _order = 'kind, sequence, id'
    name = fields.Char(required=True, string='Nombre del informe')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10, string='Orden')
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company, string='Matriz / compañía')
    kind = fields.Selection([('balance','Balance general'),('profit','Estado de resultados')],required=True,default='balance',string='Informe')
    order_by = fields.Selection([('sequence','Número de orden'),('code','Código de cuenta')],default='sequence',required=True,string='Ordenar por')
    line_ids = fields.One2many('esi.finance.layout.line','layout_id',string='Estructura')
    note = fields.Text(string='Observaciones')
    standard = fields.Boolean(readonly=True,copy=False,string='Estructura estándar')

    def action_create_standard(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise ValidationError(_('Se requieren permisos de administrador de Contabilidad.'))
        company = self.env.company
        existing = self.search([('company_id','=',company.id),('standard','=',True)])
        by_kind = {layout.kind:layout for layout in existing}
        types = self.env['esi.finance.account.type']
        for code,name in ACCOUNT_TYPES:
            if not types.search_count([('code','=',code)]):types.create({'code':code,'name':name})
        def new_layout(kind,name):
            layout = self.create({'name':name,'company_id':company.id,'kind':kind,'standard':True})
            by_kind[kind] = layout
            return layout
        def line(layout,name,code,seq,account_types,sign='1'):
            return self.env['esi.finance.layout.line'].create({'layout_id':layout.id,'name':name,'code':code,
                'sequence':seq,'mode':'account_type','sign':sign,'detail':'hierarchy',
                'account_type_ids':[(6,0,types.search([('code','in',account_types)]).ids)]})
        def formula(layout,name,code,seq,terms):
            return self.env['esi.finance.layout.line'].create({'layout_id':layout.id,'name':name,'code':code,
                'sequence':seq,'mode':'formula','style':'heading',
                'term_ids':[(0,0,{'source_id':source.id,'operation':operation}) for source,operation in terms]})
        if 'profit' not in by_kind:
            layout = new_layout('profit',_('Estado de resultados'))
            income=line(layout,_('INGRESOS'),'4',10,['income','income_other'],'-1')
            costs=line(layout,_('COSTOS'),'5',20,['expense_direct_cost'])
            expense=line(layout,_('GASTOS'),'6',30,['expense','expense_other','expense_depreciation'])
            formula(layout,_('RESULTADO DEL PERÍODO'),'R',40,[(income,'1'),(costs,'-1'),(expense,'-1')])
        if 'balance' not in by_kind:
            layout = new_layout('balance',_('Balance general'))
            assets=line(layout,_('ACTIVO'),'1',10,[c for c,n in ACCOUNT_TYPES if c.startswith('asset')])
            liability=line(layout,_('PASIVO'),'2',20,[c for c,n in ACCOUNT_TYPES if c.startswith('liability')],'-1')
            equity=line(layout,_('PATRIMONIO'),'3',30,['equity','equity_unaffected'],'-1')
            income=line(layout,_('Ingresos acumulados sin cierre'),'RA-I',900,['income','income_other'],'-1');income.visible=False
            costs=line(layout,_('Gastos acumulados sin cierre'),'RA-G',910,['expense','expense_other','expense_depreciation','expense_direct_cost']);costs.visible=False
            earnings=formula(layout,_('RESULTADO ACUMULADO SIN CIERRE'),'RA',40,[(income,'1'),(costs,'-1')])
            total=formula(layout,_('PASIVO + PATRIMONIO + RESULTADO'),'PP',50,[(liability,'1'),(equity,'1'),(earnings,'1')])
            formula(layout,_('DIFERENCIA DE CUADRE'),'D',60,[(assets,'1'),(total,'-1')])
        return {'type':'ir.actions.act_window','name':_('Estructuras financieras'),'res_model':self._name,'view_mode':'list,form','domain':[('company_id','=',company.id)]}


class FinancialLayoutLine(models.Model):
    _name = 'esi.finance.layout.line'
    _description = 'Línea configurable de estado financiero'
    _order = 'sequence, code, id'
    name = fields.Char(required=True,string='Título')
    layout_id = fields.Many2one('esi.finance.layout',required=True,ondelete='cascade',string='Informe')
    company_id = fields.Many2one(related='layout_id.company_id',store=True)
    sequence = fields.Integer(default=10,string='Orden')
    code = fields.Char(string='Código / Nº cuenta')
    parent_id = fields.Many2one('esi.finance.layout.line',ondelete='restrict',string='Título superior',domain="[('layout_id','=',layout_id)]")
    child_ids = fields.One2many('esi.finance.layout.line','parent_id',string='Subtítulos')
    mode = fields.Selection([('sum','Suma de hijos'),('accounts','Cuentas seleccionadas'),('account_type','Tipos de cuentas'),
        ('reference','Valor de otro título / informe'),('formula','Fórmula suma/resta')],default='sum',required=True,string='Origen del valor')
    sign = fields.Selection([('1','Conservar signo'),('-1','Invertir signo')],default='1',required=True,string='Signo')
    detail = fields.Selection([('none','Sin detalle'),('flat','Cuentas en lista'),('hierarchy','Cuentas con jerarquía')],default='flat',required=True,string='Detalle')
    account_ids = fields.Many2many('account.account',string='Cuentas',context={'active_test':False})
    include_account_children = fields.Boolean(default=True,string='Incluir subcuentas')
    account_type_ids = fields.Many2many('esi.finance.account.type',string='Tipos contables')
    reference_id = fields.Many2one('esi.finance.layout.line',string='Título / informe referenciado',ondelete='restrict',domain="[('company_id','=',company_id)]")
    term_ids = fields.One2many('esi.finance.layout.term','line_id',string='Operaciones')
    excluded_journal_ids = fields.Many2many('account.journal',string='Excluir diarios')
    style = fields.Selection([('auto','Automático'),('heading','Título principal'),('bold','Negrita'),('normal','Normal'),('italic','Cursiva'),('small','Texto pequeño')],default='auto',required=True,string='Estilo')
    visible = fields.Boolean(default=True,string='Mostrar en el informe')

    @api.constrains('parent_id','layout_id','reference_id','company_id')
    def _validate_links(self):
        for line in self:
            if line.parent_id and line.parent_id.layout_id != line.layout_id:
                raise ValidationError(_('El título superior debe pertenecer al mismo informe.'))
            if line.reference_id and line.reference_id.company_id != line.company_id:
                raise ValidationError(_('La referencia debe pertenecer a la misma compañía.'))
            seen={line.id};parent=line.parent_id
            while parent:
                if parent.id in seen:raise ValidationError(_('La jerarquía no puede contener ciclos.'))
                seen.add(parent.id);parent=parent.parent_id


class FinancialLayoutTerm(models.Model):
    _name = 'esi.finance.layout.term'
    _description = 'Operación de fórmula financiera'
    _order = 'sequence,id'
    sequence = fields.Integer(default=10,string='Orden')
    line_id = fields.Many2one('esi.finance.layout.line',required=True,ondelete='cascade')
    company_id = fields.Many2one(related='line_id.company_id',store=True)
    source_id = fields.Many2one('esi.finance.layout.line',required=True,ondelete='restrict',string='Título / informe',domain="[('company_id','=',company_id)]")
    operation = fields.Selection([('1','Sumar'),('-1','Restar')],default='1',required=True,string='Operación')

    @api.constrains('source_id','line_id')
    def _validate_company(self):
        for term in self:
            if term.source_id.company_id != term.company_id:
                raise ValidationError(_('Las fórmulas deben referenciar informes de la misma compañía.'))
