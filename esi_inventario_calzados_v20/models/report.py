import io
from html import escape
import xlsxwriter
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from .matrix import build_matrix


class ShoeInventoryReport(models.TransientModel):
    _name = 'esi.shoe.inventory.report'
    _inherit = 'esi.report.mixin'
    _description = 'Kardex por talla'

    company_id = fields.Many2one('res.company', string='Sucursal / compañía', required=True, default=lambda s: s.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', required=False,
        domain="[('company_id', 'in', report_company_ids)]",
        default=False)
    category_id = fields.Many2one('product.category', string='Categoría y descendientes',
        default=lambda s: s.env['product.category'].search([('name','=ilike','Producto terminado'),('parent_id','=',False)],limit=1))
    template_id = fields.Many2one('product.template', string='Producto', domain="[('esi_manufacture_ok','=',True), '|', ('company_id','=',False), ('company_id','in',report_company_ids)]")
    size_attribute_id = fields.Many2one('product.attribute', string='Atributo de talla', required=True,
        default=lambda s: s.env['product.attribute'].search([('name','=ilike','Talla')],limit=1))
    quantity_type = fields.Selection([('physical','Existencia física'),('free','Disponible sin reservas')],
        string='Cantidad', default='physical', required=True)
    include_zero = fields.Boolean(string='Incluir productos sin existencias')

    @api.onchange('company_id')
    def _onchange_company(self):
        self.warehouse_id = False
        self.template_id = False
        self.preview = False

    @api.onchange('warehouse_id','category_id','template_id','size_attribute_id','quantity_type','include_zero')
    def _clear_preview(self):
        self.preview = False

    def _report_data_single(self):
        self.ensure_one()
        self.check_access('read')
        if self._scope_company() not in self.env.companies:
            raise UserError(_('Active la sucursal seleccionada antes de consultar.'))
        warehouses = self.warehouse_id or self.env['stock.warehouse'].search([('company_id','=',self._scope_company().id)])
        warehouses.check_access('read')
        if any(w.company_id != self._scope_company() for w in warehouses):
            raise UserError(_('Seleccione un almacén del ámbito elegido.'))
        if not self.size_attribute_id:
            raise UserError(_('Seleccione el atributo Talla.'))
        domain = [('esi_manufacture_ok','=',True), ('is_storable','=',True),
                  '|', ('company_id','=',False), ('company_id','=',self._scope_company().id)]
        if self.category_id:
            self.category_id.check_access('read')
            domain.append(('categ_id','child_of',self.category_id.id))
        if self.template_id:
            self.template_id.check_access('read')
            domain.append(('product_tmpl_id','=',self.template_id.id))
        products = self.env['product.product'].with_company(self._scope_company()).with_context(active_test=False).search(domain, limit=20001)
        if len(products)>20000:
            raise UserError(_('Hay más de 20.000 variantes. Filtre por categoría o producto.'))
        quants = self.env['stock.quant'].with_company(self._scope_company())._read_group([
            ('company_id','=',self._scope_company().id), ('product_id','in',products.ids),
            ('location_id','child_of',warehouses.mapped('view_location_id').ids),
            ('location_id.usage','=','internal'), ('owner_id','=',False)],
            ['product_id'], ['quantity:sum','reserved_quantity:sum'])
        quantities = {p.id:qty - reserved if self.quantity_type == 'free' else qty for p,qty,reserved in quants}
        entries = []
        for p in products:
            qty = quantities.get(p.id,0.0)
            values = p.product_template_attribute_value_ids
            size = values.filtered(lambda v: v.attribute_id == self.size_attribute_id)
            if len(size)>1:
                raise UserError(_('La variante %s tiene más de una talla.',p.display_name))
            label = size.product_attribute_value_id.name if size else 'Sin talla'
            others = values - size
            description = p.product_tmpl_id.name
            if others:
                description += ' · ' + ' / '.join('%s: %s' % (v.attribute_id.name,v.product_attribute_value_id.name) for v in others.sorted('id'))
            code = p.default_code or p.product_tmpl_id.default_code or ''
            suffix = '-T' + label
            if code.endswith(suffix): code = code[:-len(suffix)]
            entries.append({'template':p.product_tmpl_id.id,'attributes':sorted(others.ids),
                'unit':p.uom_id.name,'size':label,'name':description,'code':code,
                'qty':qty,'cost':p.standard_price})
        headers, rows = build_matrix(entries,self.include_zero)
        title = 'Kardex por talla · %s · %s · %s · %s · %s' % (
            self._scope_company().name,', '.join(warehouses.mapped('name')),
            'Existencia física' if self.quantity_type == 'physical' else 'Disponible sin reservas',
            self._scope_company().currency_id.name,fields.Datetime.context_timestamp(self,fields.Datetime.now()).strftime('%d/%m/%Y %H:%M'))
        return title,headers,rows

    def _html(self,title,headers,rows):
        def cell(v):
            return escape(('%g' % v) if isinstance(v,(float,int)) else str(v or ''))
        html = '<h3>%s</h3><p>PU: costo actual por unidad. Existencias propias actuales, sin consignación. Variable: las tallas tienen costos distintos.</p>' % escape(title)
        html += '<table class="table table-sm table-bordered" style="font-size:9px;width:100%"><thead><tr>'
        html += ''.join('<th>%s</th>'%cell(h) for h in headers)+'</tr></thead><tbody>'
        for row in rows:
            html += '<tr%s>' % (' style="font-weight:bold"' if row[headers.index('Descripción')]=='TOTAL' else '')
            html += ''.join('<td>%s</td>'%cell(v) for v in row)+'</tr>'
        return html+'</tbody></table>'

    def action_xlsx(self):
        self.ensure_one()
        title,headers,rows = self._report_data()
        out = io.BytesIO()
        book = xlsxwriter.Workbook(out,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
        sheet = book.add_worksheet('Kardex por talla')
        head = book.add_format({'bold':True,'bg_color':'#072955','font_color':'white','border':1})
        num = book.add_format({'num_format':'#,##0.###;[Red]-#,##0.###;"-"','border':1})
        money = book.add_format({'num_format':'#,##0.00','border':1})
        text = book.add_format({'border':1})
        total = book.add_format({'bold':True,'bg_color':'#E2EFDA','num_format':'#,##0.###','border':1})
        sheet.merge_range(0,0,0,len(headers)-1,title,head)
        sheet.merge_range(1,0,1,len(headers)-1,'PU = costo actual por unidad. Variable = costos distintos por talla. Cantidades actuales; no es un corte histórico.')
        sheet.write_row(3,0,headers,head)
        for i,row in enumerate(rows,4):
            for j,value in enumerate(row):
                fmt = total if row[headers.index('Descripción')]=='TOTAL' else money if j in (headers.index('PU'),len(headers)-1) and isinstance(value,(int,float)) else num if isinstance(value,(int,float)) else text
                sheet.write(i,j,value,fmt)
        count = sum(r[headers.index('Descripción')]!='TOTAL' for r in rows)
        if count: sheet.autofilter(3,0,3+count,len(headers)-1)
        sheet.freeze_panes(4,headers.index('Descripción')+1)
        sheet.set_column(0,len(headers)-1,12)
        sheet.set_column(headers.index('Código'),headers.index('Código'),23)
        sheet.set_column(headers.index('Descripción'),headers.index('Descripción'),72)
        first_size = headers.index('TOTAL')+1
        if first_size < len(headers)-1: sheet.set_column(first_size,len(headers)-2,8)
        sheet.set_column(len(headers)-1,len(headers)-1,17)
        sheet.set_landscape();sheet.set_paper(8);sheet.fit_to_pages(1,0);sheet.repeat_rows(0,3)
        book.close()
        self.write({'export_file':BinaryBytes(out.getvalue()),'export_name':'Kardex_por_talla.xlsx'})
        return {'type':'ir.actions.act_url','url':'/web/content/%s/%s/export_file/%s?download=true' % (self._name,self.id,self.export_name),'target':'self'}

    def action_pdf(self):
        self.ensure_one()
        return self.env.ref('esi_inventario_calzados_v20.report_inventory').report_action(self)


class InventoryDocument(models.AbstractModel):
    _name = 'report.esi_inventario_calzados_v20.document'
    _description = 'PDF de inventario por talla'

    def _get_report_values(self,docids,data=None):
        docs = self.env['esi.shoe.inventory.report'].browse(docids).exists()
        docs.check_access('read')
        if len(docs)!=1 or docs.create_uid != self.env.user:
            raise UserError(_('Seleccione un informe propio.'))
        title,headers,rows = docs._report_data()
        if len(headers)>30:
            raise UserError(_('Para más de 24 tallas utilice Excel o filtre por producto.'))
        return {'docs':docs,'doc_ids':docs.ids,'doc_model':docs._name,'body':Markup(docs._html(title,headers,rows))}
