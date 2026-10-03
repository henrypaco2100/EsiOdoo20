from datetime import datetime, time, timedelta
import pytz
from odoo import fields, models, _
from odoo.exceptions import UserError
class Report(models.TransientModel):
    _name = 'esi.production.report'
    _inherit = 'esi.report.mixin'
    _description = 'Informe de producción ESI'
    company_id = fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    date_from = fields.Date(required=True,default=lambda s:fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True,default=fields.Date.today)
    group_id = fields.Many2one('esi.production.group',string='Grupo')
    kind = fields.Selection([('summary','Resumen de órdenes'),('shortage','Necesidad no reservada'),('piecework','Destajos'),('cost','Costos nativos de producción')],required=True,default='summary')
    def _report_data(self):
        self.ensure_one();self.check_access('read')
        if self.company_id not in self.env.companies or self.date_from>self.date_to:raise UserError(_('Revise compañía y fechas.'))
        tz=pytz.timezone(self.env.user.tz or 'UTC')
        start=tz.localize(datetime.combine(self.date_from,time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end=tz.localize(datetime.combine(self.date_to+timedelta(days=1),time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        domain=[('company_id','=',self.company_id.id),('date_start','>=',start),('date_start','<',end)]
        if self.group_id:domain.append(('esi_group_id','=',self.group_id.id))
        orders=self.env['mrp.production'].search(domain,limit=10001)
        if len(orders)>10000:raise UserError(_('Reduzca el período.'))
        title='Producción ESI · %s / %s' % (self.date_from,self.date_to)
        if self.kind=='summary':
            return title,['OF','Grupo','Producto','Cantidad','Unidad','Estado','Encargado','Sucursal'],[[o.name,o.esi_group_id.name or '',o.product_id.display_name,o.product_qty,o.uom_id.name,o.state,o.esi_responsible_id.name or '',o.esi_store_id.name or ''] for o in orders]
        if self.kind=='piecework':
            dd=[('company_id','=',self.company_id.id),('date','>=',self.date_from),('date','<=',self.date_to)]
            if self.group_id:dd.append(('group_id','=',self.group_id.id))
            ds=self.env['esi.destajo'].search(dd)
            return title,['Destajo','OF','Operador','Actividad','Cantidad','Tarifa','Total','Moneda'],[[d.name,d.production_id.name,d.operator_id.name,d.activity,d.quantity,d.unit_price,d.amount_total,d.currency_id.name] for d in ds]
        if self.kind=='cost':
            if not self.env.user.has_group('mrp.group_mrp_manager'):
                raise UserError(_('El análisis de costos requiere el rol de responsable de fabricación.'))
            rows=[]
            for o in orders:
                material=abs(sum(o.move_raw_ids.filtered(lambda m:m.state=='done').mapped('value')))
                finished=sum(o.move_finished_ids.filtered(lambda m:m.state=='done').mapped('value'))
                destajos=sum(self.env['esi.destajo'].search([('production_id','=',o.id)]).mapped('amount_total'))
                rows.append([o.name,o.product_id.display_name,o.state,material,finished,destajos,o.company_id.currency_id.name])
            return title+' · Destajos informativos, no sumados a valoración',['OF','Producto','Estado','Material consumido valor nativo','Producto y subproductos valor nativo','Destajos registrados','Moneda'],rows
        rows=[]
        for o in orders:
            for m in o.move_raw_ids.filtered(lambda m:m.state not in ('done','cancel')):
                pending=max(0,m.product_uom_qty-m.quantity)
                rows.append([o.name,m.product_id.display_name,m.uom_id.name,m.product_uom_qty,m.quantity,pending])
        return title+' · No reservado; no equivale a falta física total',['OF','Material','Unidad','Necesario','Reservado / recogido','Pendiente'],rows
