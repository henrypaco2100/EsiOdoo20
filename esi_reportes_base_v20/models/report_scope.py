from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReportScope(models.AbstractModel):
    _inherit = 'esi.report.mixin'

    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    report_company_ids = fields.Many2many('res.company', compute='_compute_report_companies', string='Compañías incluidas')

    def _report_companies(self):
        self.ensure_one()
        assigned = self.env.user.company_ids
        if not self.company_id or self.company_id not in assigned:
            raise UserError(_('Compañía no autorizada para este usuario.'))
        # The report may include inactive-in-session children, but only those
        # explicitly assigned to the user. No sudo or record-rule bypass.
        companies = self.env['res.company'].with_context(allowed_company_ids=assigned.ids).search([
            ('id','child_of',self.company_id.id), ('id','in',assigned.ids)])
        return companies

    @api.depends('company_id')
    @api.depends_context('uid','allowed_company_ids')
    def _compute_report_companies(self):
        for report in self:
            report.report_company_ids = report._report_companies() if report.company_id and report.company_id in report.env.user.company_ids else False

    @api.onchange('company_id')
    def _clear_scope_output(self):
        self.preview = False
        self.export_file = False
        self.export_name = False

    def _scope_company(self):
        companies = self._report_companies()
        company = self.env['res.company'].browse(self.env.context.get('esi_report_company_id') or self.company_id.id)
        if company not in companies:
            raise UserError(_('La sucursal solicitada no pertenece al ámbito autorizado.'))
        return company

    def _scope_records(self, field):
        records = self[field]
        company = self._scope_company()
        return records.filtered(lambda r: not r.company_id or r.company_id == company)

    def _report_data(self):
        self.ensure_one()
        self.check_access('read')
        companies = self._report_companies()
        report = self.with_context(allowed_company_ids=companies.ids)
        # Check filters against the complete scope before splitting by company.
        for name in ('warehouse_id','warehouse_ids','location_ids','product_ids','template_id',
                     'lot_ids','group_id','production_id','workcenter_id'):
            if name not in self._fields or not self[name]:
                continue
            records = report[name]
            records.check_access('read')
            if 'company_id' in records._fields and any(r.company_id and r.company_id not in companies for r in records):
                raise UserError(_('El filtro %s pertenece a otra compañía.', self._fields[name].string))
        results = []
        for company in companies.sorted('id'):
            skip = False
            for name in ('warehouse_id','warehouse_ids','group_id','production_id','workcenter_id','location_ids','lot_ids'):
                if name in self._fields and self[name] and all(r.company_id and r.company_id != company for r in self[name]):
                    skip = True
            if skip:
                continue
            part = report.with_company(company).with_context(esi_report_company_id=company.id)
            if self._name in ('esi.kardex.report','esi.shoe.inventory.report') and not part.env['stock.warehouse'].search_count([('company_id','=',company.id)]):
                continue
            title,headers,rows = part._report_data_single()
            results.append((company,title,headers,rows))
        if not results:
            raise UserError(_('No hay almacenes o entidades accesibles que coincidan con los filtros.'))
        if len(results)==1:
            company,title,headers,rows=results[0]
            return title+' · '+company.name,headers,rows
        headers = list(results[0][2])
        for company,title,cols,rows in results:
            for col in cols:
                if col not in headers: headers.append(col)
        if self._name == 'esi.shoe.inventory.report':
            from decimal import Decimal, InvalidOperation
            fixed = ['Código','Descripción','Unidad','PU','TOTAL','Valor']
            def sort_size(value):
                try: return (0,Decimal(value.replace(',','.')),value)
                except InvalidOperation: return (1,Decimal(0),value)
            headers=fixed[:-1]+sorted([c for c in headers if c not in fixed],key=sort_size)+['Valor']
        merged=[]
        for company,title,cols,rows in results:
            for row in rows:
                values=dict(zip(cols,row))
                prefix=[company.name,company.currency_id.name] if self._name=='esi.shoe.inventory.report' else [company.name]
                merged.append(prefix+[values.get(h,0.0 if self._name=='esi.shoe.inventory.report' else '') for h in headers])
        title='%s · %s · Incluye: %s' % (self._description,self.company_id.name,', '.join(c.name for c,t,h,r in results))
        if 'date_from' in self._fields: title+=' · %s / %s' % (self.date_from,self.date_to)
        prefix=['Sucursal / compañía','Moneda'] if self._name=='esi.shoe.inventory.report' else ['Sucursal / compañía']
        return title,prefix+headers,merged
