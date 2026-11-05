from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from markupsafe import Markup, escape
from odoo import fields, models, _
from odoo.exceptions import UserError


def period_start(day, grouping):
    if grouping == 'week':
        return day - timedelta(days=day.weekday())
    if grouping == 'month':
        return day.replace(day=1)
    if grouping == 'year':
        return day.replace(month=1, day=1)
    return day


class CenterAdvance(models.Model):
    _name = 'esi.center.advance'
    _description = 'Registro de avance por centro'
    _order = 'advanced_at, id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    workorder_id = fields.Many2one('mrp.workorder', ondelete='restrict', required=True)
    workcenter_id = fields.Many2one('mrp.workcenter', ondelete='restrict', required=True)
    advanced_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    quantity = fields.Float(required=True, digits=(16, 2))
    uom_id = fields.Many2one('uom.uom', required=True, ondelete='restrict')
    operator_id = fields.Many2one('res.users', required=True)


class CenterReport(models.TransientModel):
    _name = 'esi.center.advance.report'
    _description = 'Matriz de producción por centro'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(required=True, default=fields.Date.context_today, string='Desde')
    date_to = fields.Date(required=True, default=fields.Date.context_today, string='Hasta')
    grouping = fields.Selection([('day', 'Día'), ('week', 'Semana'), ('month', 'Mes'), ('year', 'Año')],
                                required=True, default='day', string='Agrupar por')
    uom_id = fields.Many2one("uom.uom", string="Unidad para tabla dinámica")
    result_html = fields.Html(readonly=True, string='Matriz')

    def _report_scope(self):
        self.ensure_one()
        self.check_access('write')
        if self.company_id not in self.env.companies:
            raise UserError(_('Seleccione una compañía activa.'))
        if not self.date_from or not self.date_to or self.date_from > self.date_to:
            raise UserError(_('Revise las fechas del informe.'))
        tz = ZoneInfo(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        utc = ZoneInfo('UTC')
        def boundary(day):
            return datetime.combine(day, time.min, tz).astimezone(utc).replace(tzinfo=None)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('advanced_at', '>=', boundary(self.date_from)),
            ('advanced_at', '<', boundary(self.date_to + timedelta(days=1))),
        ]
        return domain, tz, utc

    def action_pivot(self):
        domain, tz, utc = self._report_scope()
        if not self.uom_id:
            raise UserError(_('Seleccione la unidad para la tabla dinámica.'))
        domain.append(('uom_id', '=', self.uom_id.id))
        pivot = self.env.ref('esi_calzados_v20.center_advance_pivot')
        return {
            'type': 'ir.actions.act_window', 'name': _('Avances por centro · %s', self.uom_id.display_name),
            'res_model': 'esi.center.advance', 'view_mode': 'pivot', 'views': [(pivot.id, 'pivot')],
            'domain': domain, 'context': dict(self.env.context, tz=tz.key,
                pivot_row_groupby=['advanced_at:' + self.grouping],
                pivot_column_groupby=['workcenter_id'], pivot_measures=['quantity']),
        }

    def action_preview(self):
        domain, tz, utc = self._report_scope()
        events = self.env['esi.center.advance'].search(domain)
        matrices = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        for event in events:
            local_day = event.advanced_at.replace(tzinfo=utc).astimezone(tz).date()
            matrices[event.uom_id][period_start(local_day, self.grouping)][event.workcenter_id] += event.quantity
        parts = []
        colors = ('#072955', '#00793a', '#244136', '#183c68')
        for unit, rows in matrices.items():
            centers = sorted({center for row in rows.values() for center in row},
                             key=lambda center: (center.sequence, center.id))
            totals = {center: sum(row.get(center, 0) for row in rows.values()) for center in centers}
            peak = max(totals.values(), default=0)
            parts.append(Markup('<h3>Tablero de avances · {}</h3><p>Centros con actividad: <strong>{}</strong> · Períodos con actividad: <strong>{}</strong></p><h4>Volumen por centro</h4><table class="table table-sm"><tbody>').format(escape(unit.name), len(centers), len(rows)))
            for center in sorted(centers, key=lambda c: (-totals[c], c.id)):
                percent = 100 * totals[center] / peak if peak else 0
                parts.append(Markup('<tr><th style="width:25%">{}</th><td style="width:60%"><div style="background:#009846;height:16px;width:{}%;border-radius:3px"></div></td><td class="text-end">{:,.2f}</td></tr>').format(escape(center.name), f'{percent:.3f}', totals[center]))
            parts.append(Markup('</tbody></table><h4>Actividad por período y centro</h4><p>El color más intenso indica mayor cantidad dentro de la misma columna.</p>'))
            peaks = {center: max(row.get(center, 0) for row in rows.values()) for center in centers}
            parts.append(Markup('<h4>Unidad: {}</h4><div style="overflow-x:auto"><table class="table table-sm table-bordered"><thead><tr><th>Período</th>').format(escape(unit.name)))
            for index, center in enumerate(centers):
                parts.append(Markup('<th style="background:{};color:white">{}</th>').format(colors[index % len(colors)], escape(center.name)))
            parts.append(Markup('</tr></thead><tbody>'))
            def append_row(label, values, tag='td'):
                cell = Markup('<th>{}</th>' if tag == 'th' else '<td>{}</td>')
                parts.extend([Markup('<tr>'), cell.format(escape(label))])
                parts.extend(cell.format(f'{value:,.2f}'.rstrip('0').rstrip('.')) for value in values)
                parts.append(Markup('</tr>'))
            for day, row in sorted(rows.items()):
                label = {'day': '%d/%m/%Y', 'week': 'Desde %d/%m/%Y',
                         'month': '%m/%Y', 'year': '%Y'}[self.grouping]
                parts.append(Markup('<tr><th>{}</th>').format(day.strftime(label)))
                for center in centers:
                    value = row.get(center, 0)
                    intensity = value / peaks[center] if peaks[center] else 0
                    palette = ('#ffffff', '#e9f4ec', '#c0e5cb', '#88cba2', '#43946b')
                    level = min(4, max(1, int(intensity * 4 + 0.999))) if value else 0
                    parts.append(Markup('<td style="background:{};color:#0b1c30;text-align:right">{}</td>').format(palette[level], f'{value:,.2f}'.rstrip('0').rstrip('.')))
                parts.append(Markup('</tr>'))
            totals = [sum(row.get(center, 0) for row in rows.values()) for center in centers]
            append_row('TOTAL', totals, 'th')
            append_row('PROMEDIO POR PERÍODO CON AVANCES', [v / len(rows) for v in totals], 'th')
            parts.append(Markup('</tbody></table></div>'))
        self.result_html = Markup('').join(parts) if parts else Markup('<p>{}</p>').format(_('No hay avances registrados para el período seleccionado.'))
        return {'type': 'ir.actions.act_window', 'name': _('Matriz de producción por centro'),
                'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'current'}
