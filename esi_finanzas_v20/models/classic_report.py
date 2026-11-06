import io
from html import escape
from collections import defaultdict
import xlsxwriter
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from .classic_hierarchy import build_hierarchy


class ClassicalFinance(models.TransientModel):
    _inherit = 'esi.finance.report'

    classic_branch_id = fields.Many2one('res.company', string='Sucursal específica',
        help='Vacío: matriz y descendientes autorizadas. Seleccione una sucursal para consultar solo su ámbito.')
    classic_journal_ids = fields.Many2many('account.journal', string='Diarios')
    classic_depth = fields.Selection([('0','Todos los niveles'),('1','Nivel 1'),('2','Hasta nivel 2'),
        ('3','Hasta nivel 3'),('4','Hasta nivel 4'),('5','Hasta nivel 5')], default='0', required=True, string='Detalle de cuentas')
    classic_show_zero = fields.Boolean(string='Mostrar cuentas sin movimiento', default=False)
    classic_assigned_ids = fields.Many2many('res.company', compute='_compute_classic_assigned')

    @api.depends_context('uid')
    def _compute_classic_assigned(self):
        for report in self:
            report.classic_assigned_ids = self.env.user.company_ids

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            # Report scope is intentionally not limited to session-active branches.
            for node in arch.xpath(".//field[@name='company_id' and not(ancestor::field)]"):
                node.set('invisible', 'False')
                node.set('domain', "[('id','in',classic_assigned_ids)]")
        return arch, view

    @api.onchange('company_id', 'classic_branch_id', 'date_from', 'date_to', 'kind',
                  'classic_journal_ids', 'account_ids', 'classic_depth', 'classic_show_zero', 'posted_only')
    def _classic_clear_preview(self):
        self.preview = False
        self.export_file = False
        if self.classic_branch_id and self.company_id:
            assigned = self.env.user.company_ids
            children = self.env['res.company'].with_context(allowed_company_ids=assigned.ids).search([
                ('id','child_of',self.company_id.id),('id','in',assigned.ids)])
            if self.classic_branch_id not in children:
                self.classic_branch_id = False

    def _report_companies(self):
        companies = super()._report_companies()
        if self.classic_branch_id:
            if self.classic_branch_id not in companies:
                raise UserError(_('La sucursal seleccionada no pertenece a la matriz o no está autorizada.'))
            companies = companies.filtered(lambda c: c.id == self.classic_branch_id.id or
                str(self.classic_branch_id.id) in (c.parent_path or '').split('/'))
        return companies

    def _classic_payload(self):
        self.ensure_one()
        self.check_access('read')
        if not self.date_from or not self.date_to or self.date_from > self.date_to:
            raise UserError(_('Revise las fechas del informe.'))
        companies = self._report_companies()
        if any(c.currency_id != self.company_id.currency_id for c in companies):
            raise UserError(_('No se consolidan compañías con monedas diferentes.'))
        report = self.with_context(allowed_company_ids=companies.ids).with_company(self.company_id)
        if any(j.company_id not in companies for j in self.classic_journal_ids):
            raise UserError(_('Hay diarios de otra sucursal en los filtros.'))
        domain = [('company_id','in',companies.ids),('date','<=',self.date_to),
                  ('display_type','not in',['line_section','line_note']),
                  ('parent_state','=', 'posted')] if self.posted_only else [
                  ('company_id','in',companies.ids),('date','<=',self.date_to),
                  ('display_type','not in',['line_section','line_note']),('parent_state','!=','cancel')]
        if self.classic_journal_ids:
            domain += [('journal_id','in',self.classic_journal_ids.ids)]
        if self.account_ids:
            self.account_ids.check_access('read')
            domain += [('account_id','child_of',self.account_ids.ids)]
        if self.partner_id:
            domain += [('partner_id','=',self.partner_id.id)]
        profit_types = ['income','income_other','expense','expense_other','expense_depreciation','expense_direct_cost']
        if self.kind == 'profit':
            domain += [('date','>=',self.date_from),('account_id.account_type','in',profit_types)]
        lines = report.env['account.move.line'].search(domain, order='date,id', limit=100001)
        if len(lines)>100000:
            raise UserError(_('El informe supera 100.000 apuntes. Reduzca el período o seleccione cuentas/diarios.'))
        totals = defaultdict(lambda:[0.,0.,0.])
        accounts = {}
        income_raw = assets = liabilities = equity = 0.
        def register(account):
            seen = set()
            while account and account.id not in seen:
                seen.add(account.id)
                accounts[account.id] = {'code':account.code or '', 'name':account.name,
                    'type':account.account_type, 'parent':account.parent_id.id}
                account = account.parent_id
        for line in lines:
            account = line.account_id
            typ = account.account_type
            if typ == 'off_balance':
                continue
            if typ in profit_types:
                income_raw += line.balance
                if self.kind == 'balance':
                    continue
            if self.kind == 'balance':
                if typ.startswith('asset'): assets += line.balance
                elif typ.startswith('liability'): liabilities -= line.balance
                elif typ.startswith('equity'): equity -= line.balance
            register(account)
            if self.kind != 'profit' and line.date < self.date_from:
                totals[account.id][0] += line.balance
            else:
                totals[account.id][1] += line.debit
                totals[account.id][2] += line.credit
        if self.classic_show_zero:
            ancestors = companies
            for company in companies:
                parent = company.parent_id
                while parent:
                    ancestors |= parent
                    parent = parent.parent_id
            account_domain = [('company_ids','in',ancestors.ids)]
            if self.account_ids: account_domain += [('id','child_of',self.account_ids.ids)]
            if self.kind == 'profit': account_domain += [('account_type','in',profit_types)]
            elif self.kind == 'balance': account_domain += [('account_type','not in',profit_types+['off_balance'])]
            for account in report.env['account.account'].with_context(active_test=False).search(account_domain):
                register(account)
        # Parent-company layout is inherited; a branch-specific order takes precedence.
        layout_company = self.classic_branch_id or self.company_id
        scope_ancestors = layout_company
        parent = layout_company.parent_id
        while parent:
            scope_ancestors |= parent
            parent = parent.parent_id
        ordering = self.env['esi.finance.classic.order'].with_context(
            allowed_company_ids=self.env.user.company_ids.ids).search([
                ('company_id','in',(scope_ancestors & self.env.user.company_ids).ids), ('kind','=',self.kind)])
        order_values = {}
        ordered_rules = sorted(ordering, key=lambda rule: (len((rule.company_id.parent_path or '').split('/')), rule.id))
        for rule in ordered_rules:
            order_values[rule.account_id.id] = rule.sequence
            if rule.label and rule.account_id.id in accounts:
                accounts[rule.account_id.id]['name'] = rule.label
        try:
            rows = build_hierarchy(accounts, totals, int(self.classic_depth), self.classic_show_zero,
                                   float(self.company_id.currency_id.rounding)/2, order_values)
        except ValueError as error:
            raise UserError(str(error)) from error
        def summary(label, value):
            return dict(code='',name=label,depth=1,group=True,amount=value,
                        opening=0.,debit=0.,credit=0.,closing=value,summary=True)
        if self.kind == 'balance':
            earnings = -income_raw
            rows += [summary(_('TOTAL ACTIVO'),assets),summary(_('TOTAL PASIVO'),liabilities),
                     summary(_('PATRIMONIO SIN RESULTADO NO CERRADO'),equity),
                     summary(_('RESULTADO ACUMULADO SIN CIERRE'),earnings),
                     summary(_('PASIVO + PATRIMONIO + RESULTADO'),liabilities+equity+earnings),
                     summary(_('DIFERENCIA DE CUADRE'),assets-liabilities-equity-earnings)]
        elif self.kind == 'profit':
            rows += [summary(_('RESULTADO DEL PERÍODO'),-income_raw)]
        title = {'balance':_('BALANCE GENERAL'),'profit':_('ESTADO DE RESULTADOS'),'trial':_('SUMAS Y SALDOS')}[self.kind]
        return {'title':title,'company':self.company_id,'companies':companies,
            'currency':self.company_id.currency_id,'date_from':self.date_from,'date_to':self.date_to,
            'posted':self.posted_only,'rows':rows,'trial':self.kind=='trial',
            'scope':', '.join(companies.mapped('name')),
            'journals':', '.join(self.classic_journal_ids.mapped('name')) or _('Todos'),
            'partial':bool(self.account_ids or self.partner_id or self.classic_journal_ids),
            'fmt':lambda value: format(value, ',.2f')}

    def _report_data(self):
        if self.kind not in ('balance','profit','trial'):
            return super()._report_data()
        p = self._classic_payload()
        headers = ['CUENTA','TÍTULO'] + (['SALDO INICIAL','DEBE','HABER','SALDO FINAL'] if p['trial'] else ['MONTO'])
        rows = [[r['code'], '  '*(r['depth']-1)+r['name']] +
                ([r['opening'],r['debit'],r['credit'],r['closing']] if p['trial'] else [r['amount']]) for r in p['rows']]
        return p['title'], headers, rows

    def _classic_html(self, payload):
        p = payload
        e = lambda value: escape(str(value))
        title = p['title']
        headers = ['CUENTA','TÍTULO'] + (['SALDO INICIAL','DEBE','HABER','SALDO FINAL'] if p['trial'] else ['MONTO'])
        content = '<h3 style="text-align:center">%s</h3><p><b>%s</b> · NIT: %s<br/>%s<br/>Expresado en %s · %s a %s</p>' % (
            e(title),e(p['company'].name),e(p['company'].vat or ''),e(p['scope']),e(p['currency'].name),e(self.date_from),e(self.date_to))
        content += '<p>Asientos: %s · Diarios: %s%s</p>' % (e('Solo publicados' if p['posted'] else 'Publicados y borradores'), e(p['journals']), ' · Informe filtrado' if p['partial'] else '')
        content += '<table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr>' + ''.join('<th style="border:1px solid #ccc;padding:6px;background:#e9ecef">%s</th>'%e(h) for h in headers)+'</tr></thead><tbody>'
        for r in p['rows']:
            style = 'font-weight:bold;' if r['group'] else ''
            content += '<tr style="%s"><td style="padding:5px;border:1px solid #ddd">%s</td><td style="padding:5px;border:1px solid #ddd;padding-left:%spx">%s</td>'%(style,e(r['code']),8+12*(r['depth']-1),e(r['name']))
            for key in (['opening','debit','credit','closing'] if p['trial'] else ['amount']):
                content += '<td style="text-align:right;border:1px solid #ddd;padding:5px;white-space:nowrap">%s</td>'%p['fmt'](r[key])
            content += '</tr>'
        return content+'</tbody></table>'

    def action_preview(self):
        if self.kind not in ('balance','profit','trial'): return super().action_preview()
        self.preview = self._classic_html(self._classic_payload())
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':self.id,'view_mode':'form','target':'new'}

    def action_pdf(self):
        if self.kind not in ('balance','profit','trial'): return super().action_pdf()
        return self.env.ref('esi_finanzas_v20.report_classic').report_action(self)

    def action_xlsx(self):
        if self.kind not in ('balance','profit','trial'): return super().action_xlsx()
        p = self._classic_payload()
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
        sheet = book.add_worksheet('Informe financiero')
        title_format = book.add_format({'bold':True,'align':'center','font_size':14})
        header = book.add_format({'bold':True,'bg_color':'#E9ECEF','border':1})
        number = book.add_format({'num_format':'#,##0.00','border':1})
        number_bold = book.add_format({'num_format':'#,##0.00','border':1,'bold':True})
        text = book.add_format({'border':1})
        bold = book.add_format({'border':1,'bold':True})
        columns = ['CUENTA','TÍTULO']+(['SALDO INICIAL','DEBE','HABER','SALDO FINAL'] if p['trial'] else ['MONTO'])
        sheet.merge_range(0,0,0,len(columns)-1,p['title'],title_format)
        sheet.merge_range(1,0,1,len(columns)-1,p['company'].name+' · NIT: '+(p['company'].vat or ''))
        sheet.merge_range(2,0,2,len(columns)-1,p['scope'])
        sheet.merge_range(3,0,3,len(columns)-1,'%s a %s · %s · %s'%(self.date_from,self.date_to,p['currency'].name,'Publicado' if p['posted'] else 'Incluye borradores'))
        sheet.write_row(5,0,columns,header)
        for i,r in enumerate(p['rows'],6):
            sheet.write_string(i,0,r['code'],bold if r['group'] else text)
            sheet.write_string(i,1,'  '*(r['depth']-1)+r['name'],bold if r['group'] else text)
            for col,key in enumerate(['opening','debit','credit','closing'] if p['trial'] else ['amount'],2):
                sheet.write_number(i,col,r[key],number_bold if r['group'] else number)
        sheet.set_column(0,0,16);sheet.set_column(1,1,65);sheet.set_column(2,len(columns)-1,20)
        sheet.freeze_panes(6,2);sheet.repeat_rows(0,5);sheet.fit_to_pages(1,0);sheet.set_paper(9)
        if p['trial']:sheet.set_landscape()
        book.close()
        self.write({'export_file':BinaryBytes(stream.getvalue()),'export_name':'Financiero_%s.xlsx'%self.kind})
        return {'type':'ir.actions.act_url','url':'/web/content/%s/%s/export_file/%s?download=true'%(self._name,self.id,self.export_name),'target':'self'}


class ClassicalDocument(models.AbstractModel):
    _name = 'report.esi_finanzas_v20.document'
    _description = 'Estados financieros jerárquicos'

    def _get_report_values(self, docids, data=None):
        docs = self.env['esi.finance.report'].browse(docids).exists()
        docs.check_access('read')
        if not docs or any(doc.create_uid != self.env.user for doc in docs):
            raise UserError(_('Este informe pertenece a otro usuario.'))
        payloads = [(doc,doc._classic_payload()) for doc in docs]
        return {'docs':docs,'payloads':payloads,'doc_ids':docs.ids,'doc_model':'esi.finance.report'}
