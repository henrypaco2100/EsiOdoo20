from collections import defaultdict
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .center_report import period_start


class CenterDashboard(models.TransientModel):
    _inherit = 'esi.center.advance.report'

    @api.model
    def get_center_dashboard(self, filters=None):
        if not self.env.user.has_group('mrp.group_mrp_user'):
            raise UserError(_('Se requieren permisos de Fabricación.'))
        filters = filters or {}
        companies = self.env.companies
        company_id = int(filters.get('company_id') or self.env.company.id)
        if company_id not in companies.ids:
            raise UserError(_('Seleccione una compañía activa y autorizada.'))
        today = fields.Date.context_today(self)
        start = fields.Date.to_date(filters.get('date_from')) if filters.get('date_from') else today - timedelta(days=29)
        end = fields.Date.to_date(filters.get('date_to')) if filters.get('date_to') else today
        grouping = filters.get('grouping') or 'day'
        if not start or not end or start > end or (end-start).days > 3660 or grouping not in ('day','week','month','year'):
            raise UserError(_('Revise el rango de fechas y la agrupación. Máximo diez años.'))
        report = self.create({'company_id':company_id,'date_from':start,'date_to':end,'grouping':grouping})
        domain, tz, utc = report._report_scope()
        units = self.env['uom.uom'].browse([
            unit.id for unit, in self.env['esi.center.advance']._read_group(
                [('company_id','=',company_id)], ['uom_id'], [])
        ])
        if not units:
            units = self.env['uom.uom'].search([('name','=ilike','PAR')],limit=1)
        unit_id = int(filters.get('uom_id') or (units[:1].id if units else 0))
        unit = self.env['uom.uom'].browse(unit_id).exists()
        if unit:
            unit.check_access('read')
        events = self.env['esi.center.advance'].search(domain+[('uom_id','=',unit_id)],limit=100001)
        if len(events)>100000:
            raise UserError(_('Hay más de 100.000 avances. Reduzca el período.'))
        workorders = self.env['mrp.workorder'].search([
            ('company_id','=',company_id),('esi_center_step','>',0),
            ('production_id.uom_id','=',unit_id),('production_id.state','in',['confirmed','progress','to_close']),
            ('state','not in',['done','cancel'])],limit=10001)
        if len(workorders)>10000:
            raise UserError(_('Hay más de 10.000 etapas pendientes.'))
        centers, series, total = {}, defaultdict(lambda: defaultdict(float)), defaultdict(float)
        finished, productions = 0, set()
        for event in events:
            center = event.workcenter_id
            centers[center.id] = center.name
            day = event.advanced_at.replace(tzinfo=utc).astimezone(tz).date()
            key = period_start(day,grouping).isoformat()
            series[key][center.id] += event.quantity
            total[center.id] += event.quantity
            mo = event.workorder_id.production_id
            productions.add(mo.id)
            stages = mo.workorder_ids.filtered('esi_center_step')
            if event.workorder_id.esi_center_step == max(stages.mapped('esi_center_step'),default=0):
                finished += event.quantity
        pending = defaultdict(float)
        for stage in workorders:
            qty = stage._esi_center_amounts()[1]
            if qty:
                centers[stage.workcenter_id.id] = stage.workcenter_id.name
                pending[stage.workcenter_id.id] += qty
        ordered = sorted(centers, key=lambda c: (centers[c],c))
        buckets = []
        cursor = start
        while cursor <= end:
            bucket = period_start(cursor,grouping).isoformat()
            if not buckets or buckets[-1]!=bucket: buckets.append(bucket)
            cursor += timedelta(days=1)
        return {
            'filters':{'company_id':company_id,'uom_id':unit_id,'date_from':start.isoformat(),'date_to':end.isoformat(),'grouping':grouping},
            'companies':[{'id':c.id,'name':c.name} for c in companies],
            'units':[{'id':u.id,'name':u.name} for u in (units | unit)],
            'unit':unit.name if unit else '',
            'kpis':{'advances':sum(total.values()),'finished':finished,'orders':len(productions),'pending':sum(pending.values())},
            'centers':[{'id':c,'name':centers[c],'advanced':total[c],'pending':pending[c]} for c in ordered],
            'periods':buckets,
            'series':[{'id':c,'name':centers[c],'values':[series[b].get(c,0) for b in buckets]} for c in ordered],
        }
