from datetime import datetime, time, timedelta
import pytz
from odoo import fields, models, _
from odoo.exceptions import UserError
class Report(models.TransientModel):
    _name = 'esi.pos.report'
    _inherit = 'esi.report.mixin'
    _description = 'POS'
    company_id = fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    date_from = fields.Date(required=True,default=lambda s:fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True,default=fields.Date.today)
    store_id = fields.Many2one('esi.store',string='Sucursal')
    partner_id = fields.Many2one('res.partner',string='Cliente / Proveedor')
    def _report_data(self):
        self.ensure_one();self.check_access('read')
        if self.company_id not in self.env.companies or self.date_from>self.date_to:raise UserError(_('Revise compañía y fechas.'))
        tz=pytz.timezone(self.env.user.tz or 'UTC')
        start=tz.localize(datetime.combine(self.date_from,time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end=tz.localize(datetime.combine(self.date_to+timedelta(days=1),time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        domain=[('company_id','=',self.company_id.id),('date_order','>=',start),('date_order','<',end)]
        if self.store_id and not self.company_id.parent_id:
            if self.env.user.esi_store_ids and self.store_id not in self.env.user.esi_store_ids:raise UserError(_('Sucursal no autorizada.'))
            domain.append(('esi_store_id','=',self.store_id.id))
        elif self.env.user.esi_store_ids and not self.company_id.parent_id:domain.append(('esi_store_id','in',self.env.user.esi_store_ids.ids))
        if self.partner_id:domain.append(('partner_id','=',self.partner_id.id))
        recs=self.env['pos.order'].search(domain,limit=20001,order='date_order,id')
        if len(recs)>20000:raise UserError(_('Reduzca el período: máximo 20.000 documentos.'))
        rows=[[r.name,str(fields.Datetime.context_timestamp(self,r.date_order)),r.partner_id.display_name or '',r.esi_store_id.display_name or '',r.state,r.currency_id.name,r.amount_total] for r in recs]
        return 'POS: '+str(self.date_from)+' / '+str(self.date_to),['Documento','Fecha local','Contacto','Sucursal','Estado','Moneda','Total'],rows
