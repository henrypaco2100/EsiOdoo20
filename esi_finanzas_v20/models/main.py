from collections import defaultdict
from datetime import timedelta
from odoo import fields, models, _
from odoo.exceptions import UserError

class MoveLine(models.Model):
    _inherit = 'account.move.line'
    esi_cash_flow = fields.Selection([('operating','Operación'),('investing','Inversión'),('financing','Financiación'),('internal','Transferencia interna')], string='Actividad de flujo de efectivo', help='Clasificación para reportes. No modifica importes, fechas ni valoración.')

class FinanceReport(models.TransientModel):
    _name = 'esi.finance.report'
    _inherit = 'esi.report.mixin'
    _description = 'Informes financieros'
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    date_from = fields.Date(required=True, default=lambda s:fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.today)
    kind = fields.Selection([('trial','Sumas y saldos'),('balance','Balance general'),('profit','Estado de resultados'),('ledger','Libro mayor'),('receivable','CxC por vencimiento'),('payable','CxP por vencimiento'),('cash','Movimientos de caja y bancos'),('cashflow','Flujo de efectivo por actividad'),('statement','Estado de cuenta de contacto'),('analytic','Resultado analítico'),('executive','Resumen ejecutivo'),('tax','Resumen de apuntes de impuestos')], required=True, default='trial')
    include_branches = fields.Boolean(string='Incluir sucursales activas descendientes', default=True, help='La jerarquía se incluye automáticamente; campo conservado por compatibilidad.')
    store_id = fields.Many2one('esi.store', string='Sucursal')
    analytic_id = fields.Many2one('account.analytic.account', string='Cuenta analítica')
    account_ids = fields.Many2many('account.account', string='Cuentas')
    partner_id = fields.Many2one('res.partner', string='Contacto')
    posted_only = fields.Boolean(default=True, string='Solo asientos publicados')

    def _report_data(self):
        self.ensure_one();self.check_access('read')
        if self.company_id not in self.env.user.company_ids or self.date_from > self.date_to:
            raise UserError(_('Revise compañía y rango de fechas.'))
        report_companies = self._report_companies()
        if any(c.currency_id != self.company_id.currency_id for c in report_companies):
            raise UserError(_('No se suman monedas distintas. Consulte esas compañías por separado.'))
        domain = [('company_id','in',report_companies.ids),('date','<=',self.date_to),('display_type','not in',['line_section','line_note'])]
        if self.posted_only:domain += [('parent_state','=','posted')]
        else:domain += [('parent_state','!=','cancel')]
        if self.account_ids:domain += [('account_id','in',self.account_ids.ids)]
        if self.partner_id:domain += [('partner_id','=',self.partner_id.id)]
        if self.kind in ('receivable','payable'):
            domain += [('account_id.account_type','=', 'asset_receivable' if self.kind=='receivable' else 'liability_payable')]
        if self.kind in ('cash','cashflow'):domain += [('account_id.account_type','=','asset_cash')]
        if self.kind in ('profit','analytic'):domain += [('account_id.account_type','in',['income','income_other','expense','expense_depreciation','expense_direct_cost'])]
        if self.kind=='analytic' and not self.analytic_id:raise UserError(_('Seleccione una cuenta analítica.'))
        if self.kind=='statement':
            if not self.partner_id:raise UserError(_('Seleccione un contacto.'))
            domain += [('account_id.account_type','in',['asset_receivable','liability_payable'])]
        if self.kind=='tax':domain += [('tax_line_id','!=',False),('date','>=',self.date_from)]
        lines = self.env['account.move.line'].with_company(self.company_id).with_context(allowed_company_ids=report_companies.ids).search(domain,order='date,id',limit=100001)
        if len(lines)>100000:raise UserError(_('El informe supera 100.000 apuntes. Reduzca las cuentas o el período.'))
        def weight(line):
            if not self.analytic_id:return 1.0
            return sum(float(v) for k,v in (line.analytic_distribution or {}).items() if str(self.analytic_id.id) in k.split(','))/100
        title = '%s · %s · %s a %s · %s' % (dict(self._fields['kind'].selection)[self.kind],self.company_id.name,self.date_from,self.date_to,self.company_id.currency_id.name)
        title += ' · Entidades: ' + ', '.join(report_companies.mapped('name'))
        if self.analytic_id:title += ' · Importe proporcional a la distribución analítica'
        rows=[]
        if self.kind=='cashflow':
            values=defaultdict(lambda:[0.0,0.0]);opening=0.0
            labels=dict(self.env['account.move.line']._fields['esi_cash_flow'].selection)
            for line in lines:
                factor=weight(line)
                if line.date<self.date_from:opening+=line.balance*factor
                else:
                    key=labels.get(line.esi_cash_flow,'Sin clasificar')
                    values[key][0]+=line.debit*factor;values[key][1]+=line.credit*factor
            rows=[['Saldo inicial',0.0,0.0,opening]]
            rows += [[name,inc,out,inc-out] for name,(inc,out) in values.items()]
            change=sum(inc-out for inc,out in values.values())
            rows += [['Cambio neto',sum(v[0] for v in values.values()),sum(v[1] for v in values.values()),change],['Saldo final',0.0,0.0,opening+change]]
            return title+' · Clasifique los apuntes de liquidez para separar actividades',['Actividad','Entradas','Salidas','Neto / Saldo'],rows
        if self.kind=='tax':
            grouped=defaultdict(float)
            for line in lines:grouped[(line.tax_line_id.name,line.account_id.code)]+=line.balance*weight(line)
            return title+' · No sustituye declaraciones fiscales',['Impuesto','Cuenta','Saldo contable'],[[name,code,value] for (name,code),value in grouped.items()]
        if self.kind=='executive':
            metrics=defaultdict(float)
            for line in lines:
                factor=weight(line);typ=line.account_id.account_type
                if typ=='asset_cash':metrics['Caja y bancos al cierre']+=line.balance*factor
                if line.date>=self.date_from:
                    if typ.startswith('income'):metrics['Ingresos del período']-=line.balance*factor
                    if typ.startswith('expense'):metrics['Gastos del período']+=line.balance*factor
            metrics['Resultado del período']=metrics['Ingresos del período']-metrics['Gastos del período']
            return title,['Indicador','Importe'],[[k,v] for k,v in metrics.items()]
        if self.kind in ('receivable','payable'):
            grouped=defaultdict(lambda:[0.0]*5)
            for line in lines:
                residual = line.balance - sum(p.amount for p in line.matched_credit_ids if p.max_date <= self.date_to) + sum(p.amount for p in line.matched_debit_ids if p.max_date <= self.date_to)
                residual *= weight(line) * (1 if self.kind=='receivable' else -1)
                if self.company_id.currency_id.is_zero(residual):continue
                days=(self.date_to-(line.date_maturity or line.date)).days
                bucket=0 if days<=0 else 1 if days<=30 else 2 if days<=60 else 3 if days<=90 else 4
                grouped[(line.partner_id.id,line.partner_id.display_name or 'Sin contacto')][bucket]+=residual
            rows=[[name,*values,sum(values)] for (_,name),values in grouped.items()]
            return title,['Contacto','No vencido','1–30 días','31–60 días','61–90 días','Más de 90','Total'],rows
        sums=defaultdict(lambda:[0.0,0.0,0.0])
        accounts={}
        for line in lines:
            factor=weight(line)
            if not factor:continue
            a=line.account_id;accounts[a.id]=a
            if line.date < self.date_from:sums[a.id][0]+=line.balance*factor
            else:sums[a.id][1]+=line.debit*factor;sums[a.id][2]+=line.credit*factor
        if self.kind in ('ledger','cash','statement'):
            for aid in sorted(accounts,key=lambda i:accounts[i].code or ''):
                a=accounts[aid]; running=sums[aid][0]
                rows.append([a.code,a.name,'','Saldo inicial','','',0.0,0.0,running])
                for line in lines.filtered(lambda l:l.account_id.id==aid and l.date>=self.date_from):
                    f=weight(line)
                    if not f:continue
                    running+=line.balance*f
                    rows.append([a.code,a.name,str(line.date),line.move_id.name,line.company_id.name,line.partner_id.display_name or '',line.debit*f,line.credit*f,running])
            return title,['Código','Cuenta','Fecha','Asiento','Sucursal / compañía','Contacto','Debe','Haber','Saldo'],rows
        earnings=0.0
        for aid in sorted(accounts,key=lambda i:accounts[i].code or ''):
            a=accounts[aid];opening,debit,credit=sums[aid];closing=opening+debit-credit
            if self.kind=='trial':rows.append([a.code,a.name,opening,debit,credit,closing])
            elif self.kind in ('profit','analytic'):rows.append([a.code,a.name,a.account_type,credit-debit])
            elif a.account_type.startswith(('income','expense')):earnings-=closing
            elif a.account_type!='off_balance':rows.append([a.code,a.name,a.account_type,-closing if a.account_type.startswith(('liability','equity')) else closing])
        if self.kind=='balance':rows.append(['','Resultados acumulados sin cierre','equity',earnings])
        if self.kind=='trial':return title,['Código','Cuenta','Saldo inicial','Debe','Haber','Saldo final'],rows
        if self.kind in ('profit','analytic'):rows.append(['','Resultado del período','',sum(r[3] for r in rows)])
        return title,['Código','Cuenta','Tipo','Importe'],rows
