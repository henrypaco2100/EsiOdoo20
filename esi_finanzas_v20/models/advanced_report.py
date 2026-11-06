import io
from collections import defaultdict
from datetime import timedelta
from html import escape
import xlsxwriter
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from .layout_engine import evaluate_layout, analytic_weight, cashflow_rows, ZERO, add
from .classic_hierarchy import build_hierarchy


class AdvancedFinance(models.TransientModel):
    _inherit = 'esi.finance.report'

    classic_company_ids = fields.Many2many('res.company','esi_finance_company_filter_rel',string='Sucursales a incluir')
    classic_layout_id = fields.Many2one('esi.finance.layout',string='Estructura del informe')
    classic_currency_id = fields.Many2one('res.currency',required=True,default=lambda self:self.env.company.currency_id,string='Moneda del informe')
    classic_currency_method = fields.Selection([('closing','Tasa a fecha final'),('transaction','Tasa de cada movimiento')],default='closing',required=True,string='Conversión')
    classic_debit_credit = fields.Boolean(string='Mostrar débito y crédito')
    classic_display = fields.Selection([('all','Todas las cuentas'),('movement','Con movimientos o saldo inicial'),('not_zero','Saldo distinto de cero')],default='movement',required=True,string='Mostrar cuentas')
    classic_initial = fields.Boolean(default=True,string='Incluir saldo inicial')
    classic_analytic_ids = fields.Many2many('account.analytic.account','esi_finance_analytic_filter_rel',string='Cuentas analíticas')
    classic_analytic_mode = fields.Selection([('allocated','Importes distribuidos en la analítica'),('entries','Asientos completos que coinciden')],default='allocated',required=True,string='Aplicar filtros')
    classic_breakdown_analytic = fields.Boolean(string='Desglosar por analítica')
    classic_breakdown_partner = fields.Boolean(string='Desglosar por contacto')
    classic_partner_ids = fields.Many2many('res.partner',string='Contactos')
    classic_excluded_journal_ids = fields.Many2many('account.journal','esi_finance_excluded_journal_rel',string='Excluir diarios')
    classic_flow_grouping = fields.Selection([('activity','Actividad: operación, inversión y financiación'),('category','Cuentas de flujo configuradas')],default='activity',required=True,string='Agrupar flujo por')
    classic_flow_activity = fields.Selection([('operating','Operación'),('investing','Inversión'),('financing','Financiación'),('internal','Transferencia interna')],string='Actividad de flujo')
    classic_flow_ids = fields.Many2many('esi.finance.flow',string='Cuentas de flujo')
    classic_compare = fields.Boolean(string='Comparar otro período')
    classic_compare_from = fields.Date(string='Comparación desde')
    classic_compare_to = fields.Date(string='Comparación hasta')
    classic_compare_label = fields.Char(default='Comparación',string='Etiqueta de comparación')
    classic_sort = fields.Selection([('date','Fecha'),('journal_partner','Diario y contacto')],default='date',required=True,string='Orden del mayor')
    classic_ledger_style = fields.Selection([('classic','Clásico'),('minimal','Minimalista')],default='minimal',required=True,string='Formato del mayor')
    classic_show_foreign = fields.Boolean(string='Mostrar moneda e importe de origen en el mayor')

    def _report_companies(self):
        companies=super()._report_companies()
        if self.classic_company_ids:
            if any(company not in companies for company in self.classic_company_ids):
                raise UserError(_('Una sucursal seleccionada no pertenece al ámbito autorizado.'))
            ids={str(company.id) for company in self.classic_company_ids}
            companies=companies.filtered(lambda company: bool(ids & set((company.parent_path or '').split('/'))))
        return companies

    @api.depends('company_id','classic_branch_id','classic_company_ids')
    @api.depends_context('uid','allowed_company_ids')
    def _compute_report_companies(self):
        return super()._compute_report_companies()

    @api.onchange('kind','company_id')
    def _advanced_defaults(self):
        self.classic_layout_id=False
        self.classic_company_ids=False
        if self.kind not in ('balance','profit','trial','cashflow'):self.classic_compare=False
        if self.company_id:self.classic_currency_id=self.company_id.currency_id
        if self.kind in ('trial','ledger','cashflow'):self.classic_analytic_mode='entries'
        self.preview=False

    @api.onchange('classic_company_ids','classic_layout_id','classic_currency_id','classic_currency_method','classic_debit_credit',
        'classic_display','classic_initial','classic_analytic_ids','classic_analytic_mode','classic_breakdown_analytic',
        'classic_breakdown_partner','classic_partner_ids','classic_excluded_journal_ids','classic_flow_activity',
        'classic_flow_ids','classic_flow_grouping','classic_compare','classic_compare_from','classic_compare_to','classic_compare_label',
        'classic_sort','classic_ledger_style','classic_show_foreign')
    def _advanced_clear_preview(self):
        self.preview=False;self.export_file=False

    def _advanced_convert(self,value,company,date,target,cache):
        currency=company.currency_id
        if currency==target:return value
        key=(company.id,date,target.id)
        if key not in cache:
            rates=(currency|target)._get_rates(company,date)
            for curr in (currency|target):
                if curr==company.currency_id:continue
                rate,rate_date=rates.get(curr.id,(0,False))
                if not rate or not rate_date or rate_date>date:
                    raise UserError(_('Falta una tasa vigente de %s para %s al %s.',curr.name,company.display_name,date))
            cache[key]=currency._convert(1.,target,company,date,round=False)
        return value*cache[key]

    def _advanced_source(self):
        self.ensure_one();self.check_access('read')
        if not self.date_from or not self.date_to or self.date_from>self.date_to:
            raise UserError(_('Revise las fechas del informe.'))
        if self.classic_compare and (not self.classic_compare_from or not self.classic_compare_to or self.classic_compare_from>self.classic_compare_to):
            raise UserError(_('Complete las fechas del período de comparación.'))
        companies=self._report_companies()
        target=self.classic_currency_id
        if not target or not target.active:raise UserError(_('Seleccione una moneda activa para el informe.'))
        report=self.with_context(allowed_company_ids=companies.ids)
        filter_report=self.with_context(allowed_company_ids=self.env.user.company_ids.ids)
        filter_companies=companies
        for company in companies:
            parent=company.parent_id
            while parent:
                filter_companies|=parent;parent=parent.parent_id
        for journals in (report.classic_journal_ids,report.classic_excluded_journal_ids):
            journals.check_access('read')
            if any(j.company_id not in companies for j in journals):raise UserError(_('Hay diarios de otra sucursal.'))
        analytics=filter_report.classic_analytic_ids|filter_report.analytic_id
        analytics.check_access('read')
        if any(a.company_id and a.company_id not in filter_companies for a in analytics):raise UserError(_('Hay analíticas de otra sucursal.'))
        if self.classic_analytic_mode=='allocated' and len(analytics.mapped('root_plan_id'))>1:
            raise UserError(_('Para distribuir importes seleccione analíticas de un mismo plan. Para combinar planes utilice Asientos completos.'))
        partners=report.classic_partner_ids|report.partner_id
        partners.check_access('read');self.account_ids.check_access('read')
        filter_report.classic_flow_ids.check_access('read')
        if any(flow.company_id and flow.company_id not in filter_companies for flow in filter_report.classic_flow_ids):
            raise UserError(_('Hay cuentas de flujo de otra sucursal.'))
        last=max(self.date_to,self.classic_compare_to) if self.classic_compare else self.date_to
        domain=[('company_id','in',companies.ids),('date','<=',last),('display_type','not in',['line_section','line_note'])]
        domain += [('parent_state','=','posted')] if self.posted_only else [('parent_state','!=','cancel')]
        if self.classic_journal_ids:domain += [('journal_id','in',self.classic_journal_ids.ids)]
        if self.classic_excluded_journal_ids:domain += [('journal_id','not in',self.classic_excluded_journal_ids.ids)]
        entry_domain=list(domain)
        if self.kind=='cashflow':domain += [('account_id.account_type','=','asset_cash')]
        if self.account_ids:domain += [('account_id','child_of',self.account_ids.ids)]
        lines=report.env['account.move.line'].search(domain,order='date,id',limit=100001)
        if len(lines)>100000:raise UserError(_('El informe supera 100.000 apuntes. Seleccione cuentas o diarios.'))
        def matches(line):
            return ((not analytics or analytic_weight(line.analytic_distribution,analytics.ids)>0)
                and (not partners or line.partner_id in partners)
                and (not self.classic_flow_activity or line.esi_cash_flow==self.classic_flow_activity)
                and (not self.classic_flow_ids or line.esi_financial_flow_id in self.classic_flow_ids))
        entry_mode=self.classic_analytic_mode=='entries'
        if entry_mode:
            candidates=report.env['account.move.line'].search(entry_domain,order='date,id',limit=100001) if self.account_ids or self.kind=='cashflow' else lines
            if len(candidates)>100000:raise UserError(_('El filtro de asientos completos supera 100.000 apuntes. Reduzca el ámbito.'))
            matched_moves={line.move_id.id for line in candidates if matches(line)}
            lines=lines.filtered(lambda line:line.move_id.id in matched_moves)
        else:lines=lines.filtered(matches)
        ancestors=companies
        for company in companies:
            parent=company.parent_id
            while parent:
                ancestors|=parent;parent=parent.parent_id
        account_records=report.env['account.account'].with_context(active_test=False).search([('company_ids','in',ancestors.ids)])
        accounts={}
        for account in account_records|lines.account_id:
            current=account;seen=set()
            while current and current.id not in seen:
                seen.add(current.id);accounts[current.id]=dict(code=current.code or '',name=current.name,type=current.account_type,parent=current.parent_id.id)
                current=current.parent_id
        cache={}
        def collect(start,end):
            facts=[]
            for line in lines:
                if line.date>end or (self.kind=='profit' and line.date<start):continue
                opening=self.kind!='profit' and line.date<start
                if opening and not self.classic_initial and self.kind in ('trial','ledger'):continue
                factor=analytic_weight(line.analytic_distribution,analytics.ids) if not entry_mode and analytics else 1.
                date=end if self.classic_currency_method=='closing' else line.date
                debit=self._advanced_convert(line.debit*factor,line.company_id,date,target,cache)
                credit=self._advanced_convert(line.credit*factor,line.company_id,date,target,cache)
                balance=debit-credit
                values=(balance,0.,0.,balance) if opening else (0.,debit,credit,balance)
                facts.append({'account':line.account_id.id,'journal':line.journal_id.id,'values':values,
                    'line':line,'opening':opening,'date':line.date,'factor':factor,'conversion_date':date})
            return facts
        facts=collect(self.date_from,self.date_to)
        comparison=collect(self.classic_compare_from,self.classic_compare_to) if self.classic_compare else []
        return companies,target,accounts,facts,comparison,cache,collect

    def _advanced_nodes(self,layout):
        nodes={};pending=list(layout.line_ids);seen=set()
        while pending:
            line=pending.pop()
            if line.id in seen:continue
            line.check_access('read');seen.add(line.id)
            if line.company_id != layout.company_id:raise UserError(_('La fórmula referencia otra compañía.'))
            nodes[line.id]=dict(name=line.name,code=line.code or '',sequence=line.sequence,parent=line.parent_id.id,
                mode=line.mode,sign=line.sign,detail=line.detail,style=line.style,visible=line.visible,
                accounts=line.account_ids.ids,include_children=line.include_account_children,
                types=line.account_type_ids.mapped('code'),reference=line.reference_id.id,
                terms=[(t.source_id.id,int(t.operation)) for t in line.term_ids],excluded=line.excluded_journal_ids.ids)
            pending.extend(line.reference_id);pending.extend(line.term_ids.source_id)
            if line.mode=='sum':pending.extend(line.child_ids)
        roots=layout.line_ids.filtered(lambda line:not line.parent_id).ids
        return nodes,roots

    def _advanced_rows(self,accounts,facts,layout,display_override=None):
        display=display_override or self.classic_display
        tolerance=.005
        if self.kind=='cashflow':return self._advanced_cashflow(facts,display)
        if layout:
            nodes,roots=self._advanced_nodes(layout)
            try:return evaluate_layout(nodes,roots,facts,accounts,layout.order_by,int(self.classic_depth),display,tolerance)
            except ValueError as error:raise UserError(str(error)) from error
        totals=defaultdict(lambda:[0.,0.,0.]);eligible={};earnings=assets=liability=equity=0.
        profit_types={'income','income_other','expense','expense_other','expense_depreciation','expense_direct_cost'}
        for fact in facts:
            aid=fact['account'];typ=accounts[aid]['type'];opening,debit,credit,closing=fact['values']
            if typ=='off_balance':continue
            if typ in profit_types:
                earnings-=closing
                if self.kind=='balance':continue
            elif self.kind=='profit':continue
            if typ.startswith('asset'):assets+=closing
            elif typ.startswith('liability'):liability-=closing
            elif typ.startswith('equity'):equity-=closing
            totals[aid]=[totals[aid][0]+opening,totals[aid][1]+debit,totals[aid][2]+credit]
        candidates=set(totals)
        if display=='all':
            for aid,a in accounts.items():
                if a['type']=='off_balance':continue
                if self.kind=='balance' and a['type'] in profit_types:continue
                if self.kind=='profit' and a['type'] not in profit_types:continue
                if self.account_ids:
                    from .layout_engine import descendant
                    if not descendant(aid,set(self.account_ids.ids),accounts):continue
                candidates.add(aid)
        for aid in candidates:
            current=aid;seen=set()
            while current in accounts and current not in seen:
                seen.add(current);eligible[current]=accounts[current];current=accounts[current].get('parent')
        # Respect the simple account ordering configured in the previous release.
        scope=self.classic_branch_id or self.company_id;ancestors=scope
        while scope.parent_id:scope=scope.parent_id;ancestors|=scope
        rules=self.env['esi.finance.classic.order'].with_context(allowed_company_ids=self.env.user.company_ids.ids).search([
            ('company_id','in',(ancestors & self.env.user.company_ids).ids),('kind','=',self.kind)])
        order={}
        for rule in sorted(rules,key=lambda r:(len((r.company_id.parent_path or '').split('/')),r.id)):
            order[rule.account_id.id]=rule.sequence
            if rule.label and rule.account_id.id in eligible:eligible[rule.account_id.id]=dict(eligible[rule.account_id.id],name=rule.label)
        rows=build_hierarchy(eligible,totals,int(self.classic_depth),display=='all',tolerance,order)
        for row in rows:
            row.setdefault('key','account:'+row['code']+':'+row['name']);row['style']='auto'
            if self.kind=='profit' and not row['code']:row['amount']=row['closing']
        if self.kind=='trial':
            for row in rows:row['amount']=row['closing']
        if display=='not_zero':rows=[r for r in rows if abs(r['closing'])>=tolerance]
        def summary(name,value):
            return dict(key='summary:'+name,code='',name=name,depth=1,group=True,style='heading',opening=0.,debit=0.,credit=0.,closing=value,amount=value,summary=True)
        if self.kind=='balance':rows += [summary(_('TOTAL ACTIVO'),assets),summary(_('TOTAL PASIVO'),liability),summary(_('PATRIMONIO REGISTRADO'),equity),summary(_('RESULTADO ACUMULADO SIN CIERRE'),earnings),summary(_('PASIVO + PATRIMONIO + RESULTADO'),liability+equity+earnings),summary(_('DIFERENCIA DE CUADRE'),assets-liability-equity-earnings)]
        elif self.kind=='profit':rows += [summary(_('RESULTADO DEL PERÍODO'),earnings)]
        return rows

    def _advanced_cashflow(self,facts,display):
        groups={};values=[]
        labels=dict(self.env['account.move.line']._fields['esi_cash_flow'].selection)
        flow_model=self.env['esi.finance.flow'].with_context(allowed_company_ids=self.env.user.company_ids.ids)
        if self.classic_flow_grouping=='activity':
            groups={key:dict(name=name,parent=None) for key,name in labels.items()}
            groups['unclassified']=dict(name=_('Sin clasificar'),parent=None)
        elif display=='all':
            scope=self._report_companies();ancestors=scope
            for company in scope:
                parent=company.parent_id
                while parent:ancestors|=parent;parent=parent.parent_id
            for flow in flow_model.search(['|',('company_id','=',False),('company_id','in',(ancestors & self.env.user.company_ids).ids)]):
                groups[flow.id]=dict(name=flow.name,code=flow.code or '',sequence=flow.sequence,parent=flow.parent_id.id or None)
            groups['unclassified']=dict(name=_('Sin clasificar'),parent=None)
        for fact in facts:
            line=fact['line']
            if self.classic_flow_grouping=='activity':
                key=line.esi_cash_flow or 'unclassified'
                groups[key]=dict(name=labels.get(line.esi_cash_flow,_('Sin clasificar')),parent=None)
            else:
                flow=flow_model.browse(line.esi_financial_flow_id.id)
                key=flow.id or 'unclassified'
                if flow:
                    seen=set();current=flow
                    while current and current.id not in seen:
                        seen.add(current.id);groups[current.id]=dict(name=current.name,code=current.code or '',sequence=current.sequence,parent=current.parent_id.id or None)
                        current=current.parent_id
                else:groups[key]=dict(name=_('Sin clasificar'),parent=None)
            values.append(dict(values=fact['values'],opening=fact['opening'],group=key))
        try:return cashflow_rows(values,groups,display)
        except ValueError as error:raise UserError(str(error)) from error

    def _advanced_breakdowns(self,rows,accounts,facts,cache,target):
        if not (self.classic_breakdown_analytic or self.classic_breakdown_partner):return rows
        output=[];groups_cache={}
        selected_analytics=self.classic_analytic_ids|self.analytic_id
        def groups(exclusions):
            if exclusions in groups_cache:return groups_cache[exclusions]
            grouped=defaultdict(lambda:ZERO);raw=defaultdict(float)
            for fact in facts:
                if fact['journal'] in exclusions:continue
                line=fact['line'];base=fact['values'];raw[fact['account']]+=base[3]
                if self.classic_breakdown_partner:
                    label='Contacto: '+(line.partner_id.display_name or _('Sin contacto'))
                    grouped[(fact['account'],label)]=add(grouped[(fact['account'],label)],base)
                if self.classic_breakdown_analytic:
                    distribution=line.analytic_distribution or {}
                    ids={int(value) for key in distribution for value in key.split(',') if value.isdigit()}
                    analytic_records=self.env['account.analytic.account'].with_context(
                        allowed_company_ids=self._report_companies().ids).browse(list(ids)).exists()
                    for analytic in analytic_records:
                        if selected_analytics and analytic not in selected_analytics:continue
                        weight=analytic_weight(distribution,{analytic.id})
                        if not weight:continue
                        debit=self._advanced_convert(line.debit*weight,line.company_id,fact['conversion_date'],target,cache)
                        credit=self._advanced_convert(line.credit*weight,line.company_id,fact['conversion_date'],target,cache)
                        val=(debit-credit,0.,0.,debit-credit) if fact['opening'] else (0.,debit,credit,debit-credit)
                        label='Analítica: '+analytic.plan_id.name+' / '+analytic.display_name
                        grouped[(fact['account'],label)]=add(grouped[(fact['account'],label)],val)
            groups_cache[exclusions]=(grouped,raw)
            return grouped,raw
        account_keys={'account:'+a['code']+':'+a['name']:aid for aid,a in accounts.items()}
        for row in rows:
            output.append(row);aid=False
            if row['key'] in account_keys:aid=account_keys[row['key']]
            elif row['key'].startswith('detail:'):aid=int(row['key'].split(':')[-1])
            elif row['key'].startswith('account:') and row['key'].split(':')[-1].isdigit():aid=int(row['key'].split(':')[-1])
            if not aid:continue
            grouped,raw=groups(tuple(row.get('excluded_journals',())))
            sign=-1 if raw[aid] and row['amount']*raw[aid]<0 else 1
            for (key,label),value in sorted(grouped.items()):
                if key!=aid:continue
                output.append(dict(key=row['key']+':'+label,code='',name=label,depth=row['depth']+1,group=False,style='italic',
                    opening=value[0]*sign,debit=value[1],credit=value[2],closing=value[3]*sign,amount=value[3]*sign,summary=False))
        return output

    def _classic_payload(self):
        if self.kind not in ('balance','profit','trial','ledger','cashflow'):return super()._classic_payload()
        companies,currency,accounts,facts,comparison,cache,collect=self._advanced_source()
        layout=self.classic_layout_id.with_context(allowed_company_ids=self.env.user.company_ids.ids)
        if layout:
            layout.check_access('read')
            anchor=self.classic_branch_id or self.company_id;ancestors=anchor
            while anchor.parent_id:anchor=anchor.parent_id;ancestors|=anchor
            if layout.company_id not in ancestors or layout.company_id not in self.env.user.company_ids or layout.kind!=self.kind:
                raise UserError(_('Seleccione una estructura del mismo informe y de la matriz o sucursal correspondiente.'))
        if self.kind=='ledger':rows=self._advanced_ledger(accounts,facts)
        else:
            rows=self._advanced_rows(accounts,facts,layout,display_override='all' if self.classic_compare else None)
            rows=self._advanced_breakdowns(rows,accounts,facts,cache,currency)
        if self.classic_compare and self.kind!='ledger':
            other=self._advanced_rows(accounts,comparison,layout,display_override='all')
            other=self._advanced_breakdowns(other,accounts,comparison,cache,currency)
            index={r['key']:r for r in other};present={r['key'] for r in rows}
            extras=defaultdict(list)
            for row in other:
                if row['key'] in present:continue
                parents=[key for key in present if row['key'].startswith(key+':')]
                if parents:
                    extras[max(parents,key=len)].append(row)
                else:extras[None].append(row)
            aligned=[]
            for row in rows:
                aligned.append(row)
                for extra in extras.get(row['key'],[]):
                    blank=dict(extra)
                    for key in ('opening','debit','credit','closing','amount'):blank[key]=0.
                    aligned.append(blank)
            for extra in extras.get(None,[]):
                blank=dict(extra)
                for key in ('opening','debit','credit','closing','amount'):blank[key]=0.
                aligned.append(blank)
            for row in aligned:
                value=index.get(row['key'],{}).get('amount',0.)
                row['compare']=value;row['difference']=row['amount']-value
            display=self.classic_display
            keep=[]
            for row in aligned:
                show=display=='all' or row['summary'] or abs(row['compare'])>=.005
                show=show or (abs(row['amount'])>=.005 if display=='not_zero' else any(abs(row[k])>=.005 for k in ('opening','debit','credit','closing')))
                keep.append(show)
            # Retain parent headings for comparison-only activity without moving them below totals.
            stack=[]
            for i,row in enumerate(aligned):
                while stack and aligned[stack[-1]]['depth']>=row['depth']:stack.pop()
                if keep[i]:
                    for ancestor in stack:keep[ancestor]=True
                stack.append(i)
            rows=[row for row,show in zip(aligned,keep) if show]
        columns=[('code','CUENTA'),('name','TÍTULO')]
        if self.kind=='ledger':
            columns += [('date','FECHA'),('move','ASIENTO')]
            if self.classic_ledger_style=='classic':columns += [('journal','DIARIO'),('company','SUCURSAL'),('partner','CONTACTO')]
            if self.classic_breakdown_partner and self.classic_ledger_style!='classic':columns += [('partner','CONTACTO')]
            if self.classic_breakdown_analytic:columns += [('analytic','ANALÍTICA')]
            columns += [('debit','DÉBITO'),('credit','CRÉDITO'),('amount','SALDO')]
            if self.classic_show_foreign:columns += [('origin_currency','MONEDA ORIGEN'),('origin_amount','IMPORTE ORIGEN')]
        elif self.kind=='cashflow':columns += [('debit','ENTRADAS'),('credit','SALIDAS'),('amount','NETO / SALDO')]
        elif self.kind=='trial':columns += [('opening','SALDO INICIAL'),('debit','DÉBITO'),('credit','CRÉDITO'),('closing','SALDO FINAL')]
        else:
            if self.classic_debit_credit:columns += [('debit','DÉBITO'),('credit','CRÉDITO')]
            columns += [('amount','MONTO')]
        if self.classic_compare and self.kind!='ledger':columns += [('compare',self.classic_compare_label or _('Comparación')),('difference','VARIACIÓN')]
        title=layout.name if layout else {'balance':_('BALANCE GENERAL'),'profit':_('ESTADO DE RESULTADOS'),'trial':_('SUMAS Y SALDOS'),'ledger':_('LIBRO MAYOR'),'cashflow':_('FLUJO DE EFECTIVO')}[self.kind]
        notes=[]
        if self.classic_currency_method=='closing':notes.append(_('Conversión a tasa de la fecha final de cada período.'))
        else:notes.append(_('Conversión de cada movimiento a su fecha contable.'))
        if self.classic_analytic_ids or self.analytic_id:notes.append(_('Filtro analítico: %s.', 'Asientos completos' if self.classic_analytic_mode=='entries' else 'Distribución proporcional'))
        analytics=self.classic_analytic_ids|self.analytic_id
        if analytics:notes.append(_('Analíticas: %s.', ', '.join(analytics.mapped('display_name'))))
        if self.classic_partner_ids or self.partner_id:notes.append(_('Contactos: %s.', ', '.join((self.classic_partner_ids|self.partner_id).mapped('display_name'))))
        if self.classic_excluded_journal_ids:notes.append(_('Diarios excluidos: %s.', ', '.join(self.classic_excluded_journal_ids.mapped('name'))))
        if self.classic_flow_ids:notes.append(_('Cuentas de flujo: %s.', ', '.join(self.classic_flow_ids.mapped('name'))))
        if self.classic_breakdown_analytic:notes.append(_('Desgloses analíticos informativos por plan; no se suman otra vez a los totales.'))
        partial=bool(self.account_ids or self.partner_id or self.classic_partner_ids or self.classic_journal_ids or self.classic_excluded_journal_ids or self.classic_analytic_ids or self.analytic_id or self.classic_flow_ids or self.classic_flow_activity)
        return dict(title=title,company=self.company_id,companies=companies,currency=currency,date_from=self.date_from,date_to=self.date_to,
            posted=self.posted_only,rows=rows,columns=columns,trial=self.kind=='trial',scope=', '.join(companies.mapped('name')),
            journals=', '.join(self.classic_journal_ids.mapped('name')) or _('Todos'),partial=partial,notes=' '.join(notes),
            comparison=('%s / %s'%(self.classic_compare_from,self.classic_compare_to)) if self.classic_compare else '',
            fmt=lambda value:format(value,',.2f'))

    def _advanced_ledger(self,accounts,facts):
        rows=[]
        account_ids={f['account'] for f in facts}
        if self.classic_display=='all':
            from .layout_engine import descendant
            account_ids |= {aid for aid,a in accounts.items() if a['type']!='off_balance' and (not self.account_ids or descendant(aid,set(self.account_ids.ids),accounts))}
        analytic_ids={int(value) for fact in facts for key in (fact['line'].analytic_distribution or {}) for value in key.split(',') if value.isdigit()}
        analytic_names={a.id:a.display_name for a in self.env['account.analytic.account'].with_context(allowed_company_ids=self._report_companies().ids).browse(list(analytic_ids)).exists()} if self.classic_breakdown_analytic else {}
        for aid in sorted(account_ids,key=lambda aid:(accounts[aid]['code'],aid)):
            relevant=[f for f in facts if f['account']==aid];opening=sum(f['values'][0] for f in relevant)
            movements=[f for f in relevant if not f['opening']]
            closing=opening+sum(f['values'][3] for f in movements)
            if self.classic_display=='not_zero' and abs(closing)<.005:continue
            running=opening
            def row(key,name,**values):
                val=dict(key=key,code=accounts[aid]['code'],name=name,depth=1,group=False,style='normal',opening=0.,debit=0.,credit=0.,closing=running,amount=running,summary=False,
                    date='',move='',journal='',company='',partner='',analytic='',origin_currency='',origin_amount='')
                val.update(values);return val
            if self.classic_initial:rows.append(row('ledger-open:'+str(aid),accounts[aid]['name']+' — '+_('Saldo inicial'),group=True,opening=opening))
            key=(lambda f:(f['line'].journal_id.code or '',f['line'].partner_id.display_name or '',f['date'],f['line'].id)) if self.classic_sort=='journal_partner' else (lambda f:(f['date'],f['line'].id))
            for fact in sorted(movements,key=key):
                line=fact['line'];running+=fact['values'][3]
                rows.append(row('ledger:'+str(line.id),line.name or accounts[aid]['name'],date=str(line.date),move=line.move_id.name,
                    journal=line.journal_id.code,company=line.company_id.name,partner=line.partner_id.display_name or '',debit=fact['values'][1],credit=fact['values'][2],
                    analytic='; '.join('%s: %.2f%%' % (' / '.join(analytic_names.get(int(value),value) for value in key.split(',') if value.isdigit()),float(percent)) for key,percent in (line.analytic_distribution or {}).items()) if self.classic_breakdown_analytic else '',
                    origin_currency=line.currency_id.name or '',origin_amount=line.amount_currency*fact['factor']))
            rows.append(row('ledger-total:'+str(aid),_('TOTAL %s',accounts[aid]['name']),group=True,summary=True,
                debit=sum(f['values'][1] for f in movements),credit=sum(f['values'][2] for f in movements)))
        return rows

    def _report_data(self):
        if self.kind not in ('balance','profit','trial','ledger','cashflow'):return super()._report_data()
        p=self._classic_payload()
        return p['title'],[label for key,label in p['columns']],[[r.get(key,'') for key,label in p['columns']] for r in p['rows']]

    def _classic_html(self,p):
        e=lambda value:escape(str(value))
        html='<h3 style="text-align:center">%s</h3><p><b>%s</b> · NIT: %s<br/>%s<br/>%s a %s · %s<br/>%s%s</p>'%(
            e(p['title']),e(p['company'].name),e(p['company'].vat or ''),e(p['scope']),e(self.date_from),e(self.date_to),e(p['currency'].name),
            e(p['notes']),'<br/>Comparación: '+e(p['comparison']) if p['comparison'] else '')
        html+='<p>Asientos: %s · Diarios: %s%s</p>'%(e('Solo publicados' if p['posted'] else 'Publicados y borradores'),e(p['journals']),' · Informe filtrado' if p['partial'] else '')
        html+='<table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr>'+''.join('<th style="border:1px solid #ccd0d5;padding:6px;background:#e9ecef">%s</th>'%e(label) for key,label in p['columns'])+'</tr></thead><tbody>'
        for row in p['rows']:
            style=('font-weight:bold;' if row['group'] or row.get('style') in ('bold','heading') else '')+('text-decoration:underline;' if row.get('style')=='heading' else '')+('font-style:italic;' if row.get('style')=='italic' else '')+('font-size:9px;' if row.get('style')=='small' else '')
            html+='<tr style="%s">'%style
            for key,label in p['columns']:
                value=row.get(key,'');numeric=isinstance(value,(int,float));text=p['fmt'](value) if numeric else e(value)
                html+='<td style="border:1px solid #ddd;padding:5px;%s%s">%s</td>'%('text-align:right;white-space:nowrap;' if numeric else '', 'padding-left:%spx;'%(8+12*(row['depth']-1)) if key=='name' else '',text)
            html+='</tr>'
        return html+'</tbody></table>'

    def action_preview(self):
        if self.kind not in ('balance','profit','trial','ledger','cashflow'):return super().action_preview()
        self.preview=self._classic_html(self._classic_payload())
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':self.id,'view_mode':'form','target':'new'}

    def action_pdf(self):
        if self.kind not in ('balance','profit','trial','ledger','cashflow'):return super().action_pdf()
        p=self._classic_payload()
        return self.env.ref('esi_finanzas_v20.report_classic').with_context(landscape=len(p['columns'])>4).report_action(self)

    def action_xlsx(self):
        if self.kind not in ('balance','profit','trial','ledger','cashflow'):return super().action_xlsx()
        p=self._classic_payload();stream=io.BytesIO()
        book=xlsxwriter.Workbook(stream,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
        sheet=book.add_worksheet('Informe financiero');count=len(p['columns'])
        title=book.add_format({'bold':True,'align':'center','font_size':14});heading=book.add_format({'bold':True,'bg_color':'#E9ECEF','border':1})
        formats={}
        def fmt(row,numeric):
            key=(row['group'],row.get('style','auto'),numeric,min(15,row['depth']-1))
            if key not in formats:
                formats[key]=book.add_format({'border':1,'bold':row['group'] or row.get('style') in ('bold','heading'),
                    'italic':row.get('style')=='italic','underline':row.get('style')=='heading','font_size':9 if row.get('style')=='small' else 10,
                    **({'num_format':'#,##0.00'} if numeric else {'indent':min(15,row['depth']-1)})})
            return formats[key]
        metadata=[p['title'],p['company'].name+' · NIT: '+(p['company'].vat or ''),p['scope'],
            '%s a %s · %s · %s'%(self.date_from,self.date_to,p['currency'].name,'Solo publicados' if p['posted'] else 'Incluye borradores'),
            p['notes']+(' Comparación: '+p['comparison'] if p['comparison'] else ''),
            'Diarios: '+p['journals']+(' · Informe filtrado' if p['partial'] else '')]
        wrap=book.add_format({'text_wrap':True,'valign':'top'})
        for index,text in enumerate(metadata):
            sheet.merge_range(index,0,index,count-1,text,title if index==0 else wrap)
            if index in (2,4,5):sheet.set_row(index,30)
        sheet.write_row(7,0,[label for key,label in p['columns']],heading)
        for index,row in enumerate(p['rows'],8):
            for col,(key,label) in enumerate(p['columns']):
                value=row.get(key,'');numeric=isinstance(value,(int,float))
                if numeric:sheet.write_number(index,col,value,fmt(row,True))
                else:sheet.write_string(index,col,str(value or ''),fmt(row,False))
        for col,(key,label) in enumerate(p['columns']):sheet.set_column(col,col,60 if key=='name' else 18)
        sheet.freeze_panes(8,2);sheet.repeat_rows(0,7);sheet.set_paper(9);sheet.fit_to_pages(1,0)
        if count>4:sheet.set_landscape()
        book.close();self.write({'export_file':BinaryBytes(stream.getvalue()),'export_name':'Financiero_%s.xlsx'%self.kind})
        return {'type':'ir.actions.act_url','url':'/web/content/%s/%s/export_file/%s?download=true'%(self._name,self.id,self.export_name),'target':'self'}
