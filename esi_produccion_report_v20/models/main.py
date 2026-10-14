from datetime import datetime, time, timedelta
from collections import defaultdict
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Report(models.TransientModel):
    _name = 'esi.production.report'
    _inherit = 'esi.report.mixin'
    _description = 'Informe de producción'
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    date_from = fields.Date(required=True, default=lambda s: fields.Date.today().replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.today)
    date_basis = fields.Selection([('date_start', 'Inicio de fabricación'), ('date_finished', 'Finalización (solo terminadas)')], default='date_start', required=True, string='Fecha utilizada')
    group_id = fields.Many2one('esi.production.group', string='Grupo', domain="[('company_id', '=', company_id)]")
    kind = fields.Selection([('summary', 'Resumen de órdenes'), ('outputs', 'Productos terminados por talla'),
        ('shortage', 'Necesidad no reservada'), ('piecework', 'Destajos'), ('cost', 'Costos nativos de producción')], required=True, default='summary')

    @api.onchange('company_id')
    def _onchange_company_filters(self):
        self.group_id = False
        self.preview = False

    def _report_data(self):
        self.ensure_one()
        self.check_access('read')
        if self.company_id not in self.env.companies:
            raise UserError(_('Active la sucursal seleccionada en el selector superior antes de consultar.'))
        if not self.date_from or not self.date_to or self.date_from > self.date_to:
            raise UserError(_('Revise el rango de fechas.'))
        if self.group_id:
            self.group_id.check_access('read')
            if self.group_id.company_id != self.company_id:
                raise UserError(_('El grupo pertenece a otra sucursal.'))
        title = 'Producción · %s · %s / %s' % (self.company_id.name, self.date_from, self.date_to)
        if self.kind == 'piecework':
            domain = [('company_id', '=', self.company_id.id), ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
            if self.group_id:
                domain.append(('group_id', '=', self.group_id.id))
            records = self.env['esi.destajo'].search(domain, order='date,id', limit=10001)
            if len(records) > 10000:
                raise UserError(_('El reporte supera 10.000 destajos. Reduzca el período.'))
            return title + ' · Fecha del destajo', ['Destajo', 'OF', 'Operador', 'Actividad', 'Cantidad', 'Tarifa', 'Total', 'Moneda'], [
                [d.name, d.production_id.name, d.operator_id.name, d.activity, d.quantity, d.unit_price, d.amount_total, d.currency_id.name] for d in records]
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = tz.localize(datetime.combine(self.date_to + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        domain = [('company_id', '=', self.company_id.id), (self.date_basis, '>=', start), (self.date_basis, '<', end), ('state', '!=', 'cancel')]
        if self.date_basis == 'date_finished':
            domain.append(('state', '=', 'done'))
        if self.group_id:
            domain.append(('esi_group_id', '=', self.group_id.id))
        orders = self.env['mrp.production'].search(domain, order='date_start,id', limit=10001)
        if len(orders) > 10000:
            raise UserError(_('El reporte supera 10.000 órdenes. Reduzca el período.'))
        title += ' · ' + dict(self._fields['date_basis'].selection)[self.date_basis]
        labels = dict(self.env['mrp.production']._fields['state']._description_selection(self.env))
        if self.kind == 'summary':
            return title, ['OF', 'Grupo', 'Producto principal', 'Cantidad principal', 'Unidad', 'Estado', 'Encargado', 'Sucursal'], [
                [o.name, o.esi_group_id.name or '', o.product_id.display_name, o.product_qty, o.uom_id.name,
                 labels.get(o.state, o.state), o.esi_responsible_id.name or '', o.company_id.name] for o in orders]
        rows = []
        if self.kind == 'outputs':
            for order in orders:
                for move in order.move_finished_ids.filtered(lambda m: m.state != 'cancel'):
                    rows.append([order.name, order.esi_group_id.name or '', move.product_id.display_name,
                        move.product_id.esi_variant_highlight or '', move.product_uom_qty,
                        move.quantity if move.state == 'done' else 0.0, move.uom_id.name, labels.get(order.state, order.state)])
            headers = ['OF', 'Grupo', 'Producto', 'Talla / atributos', 'Planificado', 'Entrado al inventario', 'Unidad', 'Estado OF']
        elif self.kind == 'cost':
            if not self.env.user.has_group('mrp.group_mrp_manager'):
                raise UserError(_('El análisis de costos requiere el rol de responsable de fabricación.'))
            destajos = defaultdict(float)
            for d in self.env['esi.destajo'].search([('production_id', 'in', orders.ids)]):
                destajos[d.production_id.id] += d.amount_total
            for order in orders:
                material = abs(sum(order.move_raw_ids.filtered(lambda m: m.state == 'done').mapped('value')))
                finished = sum(order.move_finished_ids.filtered(lambda m: m.state == 'done').mapped('value'))
                rows.append([order.name, order.product_id.display_name, labels.get(order.state, order.state), material,
                    finished, destajos[order.id], order.company_id.currency_id.name])
            title += ' · Destajos informativos; no se suman a valoración'
            headers = ['OF', 'Producto principal', 'Estado', 'Material: valor nativo', 'Todas las salidas: valor nativo', 'Destajos', 'Moneda']
        else:
            for order in orders:
                for move in order.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                    pending = max(0, move.product_uom_qty - move.quantity)
                    if not move.uom_id.is_zero(pending):
                        rows.append([order.name, move.product_id.display_name, move.uom_id.name, move.product_uom_qty, move.quantity, pending])
            title += ' · Pendiente de reserva/recogida; no es falta física total'
            headers = ['OF', 'Material', 'Unidad', 'Necesario', 'Reservado / recogido', 'Pendiente']
        if len(rows) > 50000:
            raise UserError(_('El reporte supera 50.000 filas. Reduzca el período o seleccione un grupo.'))
        return title, headers, rows


class ProductionGroup(models.Model):
    _inherit = 'esi.production.group'

    def action_production_report(self):
        self.ensure_one()
        self.check_access('read')
        dates = [fields.Datetime.context_timestamp(self, o.date_start).date() for o in self.production_ids if o.date_start]
        return {'type': 'ir.actions.act_window', 'name': _('Informe del grupo'), 'res_model': 'esi.production.report',
            'view_mode': 'form', 'target': 'current', 'context': dict(self.env.context,
                default_company_id=self.company_id.id, default_group_id=self.id, default_kind='outputs',
                default_date_from=min(dates) if dates else fields.Date.context_today(self),
                default_date_to=max(dates) if dates else fields.Date.context_today(self))}
