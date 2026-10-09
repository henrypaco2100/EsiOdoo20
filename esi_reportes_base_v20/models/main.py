import base64
import io
from html import escape
import xlsxwriter
from markupsafe import Markup
from odoo.tools import BinaryBytes
from odoo import fields, models, _
from odoo.exceptions import UserError

class ReportMixin(models.AbstractModel):
    _name = 'esi.report.mixin'
    _description = 'Exportación de reportes'
    preview = fields.Html(string='Vista previa', readonly=True, sanitize=True)
    export_file = fields.Binary(readonly=True, attachment=False)
    export_name = fields.Char(readonly=True)
    def _report_data(self):
        raise NotImplementedError()
    def _html(self, title, headers, rows):
        cell = lambda value: escape(str(value if value is not None else ''))
        head = ''.join('<th>%s</th>' % cell(h) for h in headers)
        body = ''.join('<tr>' + ''.join('<td>%s</td>' % cell(round(v, 2) if isinstance(v, float) else v) for v in row) + '</tr>' for row in rows)
        return '<h2>%s</h2><table class="table table-sm table-striped"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (cell(title), head, body)
    def action_preview(self):
        self.ensure_one()
        self.preview = self._html(*self._report_data())
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':self.id,'view_mode':'form','target':'current'}
    def action_xlsx(self):
        self.ensure_one()
        title, headers, rows = self._report_data()
        out = io.BytesIO()
        book = xlsxwriter.Workbook(out, {'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
        sheet = book.add_worksheet('ESI')
        bold = book.add_format({'bold':True,'bg_color':'#072955','font_color':'#FFFFFF'})
        num = book.add_format({'num_format':'#,##0.00'})
        sheet.write(0,0,title)
        sheet.write_row(2,0,headers,bold)
        for i,row in enumerate(rows,3):
            for j,value in enumerate(row):
                sheet.write(i,j,value,num if isinstance(value,(float,int)) else None)
        sheet.freeze_panes(3,0);sheet.autofilter(2,0,max(2,len(rows)+2),len(headers)-1)
        sheet.set_column(0,len(headers)-1,22);book.close()
        self.write({'export_file':BinaryBytes(out.getvalue()),'export_name':'ESI_informe.xlsx'})
        return {'type':'ir.actions.act_url','url':'/web/content/%s/%s/export_file/%s?download=true' % (self._name,self.id,self.export_name),'target':'self'}
    def action_pdf(self):
        self.ensure_one()
        self.preview = self._html(*self._report_data())
        action = self.env.ref('esi_reportes_base_v20.report_document').report_action(self, data={'model':self._name,'id':self.id})
        return action

class Document(models.AbstractModel):
    _name = 'report.esi_reportes_base_v20.document'
    _description = 'Documento'
    def _get_report_values(self, docids, data=None):
        allowed = {'esi.finance.report','esi.sales.report','esi.purchase.report','esi.pos.report','esi.production.report'}
        data = data or {}
        if data.get('model') not in allowed:
            raise UserError(_('Reporte no autorizado.'))
        rec = self.env[data['model']].browse(data['id']).exists()
        rec.check_access('read')
        if not rec or rec.create_uid != self.env.user:
            raise UserError(_('Este informe pertenece a otro usuario.'))
        # Recompute under the requesting user; never trust HTML/data sent by a client.
        html = rec._html(*rec._report_data())
        return {'docs':rec,'body':Markup(html),'doc_ids':rec.ids,'doc_model':rec._name}
