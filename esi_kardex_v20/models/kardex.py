from datetime import datetime, time, timedelta
from html import escape
import io
import pytz
import xlsxwriter
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from .balances import build_ledger
from collections import defaultdict
from .valuation import movement_unit_value, reconcile_values


class Kardex(models.TransientModel):
    _name = 'esi.kardex.report'
    _inherit = 'esi.report.mixin'
    _description = 'Kardex físico (solo consulta)'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    show_valuation = fields.Boolean(string='Mostrar valoración', default=True)
    period = fields.Selection([('month', 'Este mes'), ('today', 'Hoy'), ('previous', 'Mes anterior'), ('30days', 'Últimos 30 días'), ('custom', 'Elegir fechas')], string='Período', default='month', required=True)
    date_from = fields.Date(string='Desde', required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.context_today)
    warehouse_ids = fields.Many2many('stock.warehouse', string='Almacenes', check_company=False)
    location_ids = fields.Many2many('stock.location', string='Ubicaciones y sububicaciones', check_company=False)
    product_ids = fields.Many2many('product.product', string='Productos / variantes', check_company=False)
    category_ids = fields.Many2many('product.category', string='Categorías y subcategorías')
    lot_ids = fields.Many2many('stock.lot', string='Lotes / series', check_company=False)
    uom_ids = fields.Many2many('uom.uom', string='Unidades adicionales',
        help='Añade columnas equivalentes. Solo convierte unidades con la misma unidad de referencia raíz; las incompatibles quedan vacías.')
    group_warehouse = fields.Boolean(string='Separar por almacén', default=True)
    group_category = fields.Boolean(string='Ordenar por categoría', default=True)
    separate_variants = fields.Boolean(string='Separar variantes', default=True)
    report_mode = fields.Selection([('detail', 'Movimiento por movimiento'), ('summary', 'Resumen de saldos por producto')], string='Tipo de informe', default='detail', required=True)
    details = fields.Boolean(compute='_compute_details')
    allowed_location_ids = fields.Many2many('stock.location', compute='_compute_allowed_locations')
    filter_summary = fields.Text(string='Filtros activos', compute='_compute_filter_summary')
    show_locations = fields.Boolean(string='Mostrar ubicaciones', default=True)
    own_only = fields.Boolean(string='Excluir existencias de terceros', default=True,
        help='Incluye solo operaciones sin propietario asignado. Desmarcar para incluir también consignación.')
    preview = fields.Html(string='Vista previa', readonly=True, sanitize=True)
    export_file = fields.Binary(readonly=True, attachment=False)
    export_name = fields.Char(readonly=True)

    @api.depends('report_mode')
    def _compute_details(self):
        for record in self:
            record.details = record.report_mode == 'detail'

    @api.onchange('period')
    def _onchange_period(self):
        today = fields.Date.context_today(self)
        if self.period == 'today':
            self.date_from = self.date_to = today
        elif self.period == 'month':
            self.date_from, self.date_to = today.replace(day=1), today
        elif self.period == 'previous':
            end = today.replace(day=1) - timedelta(days=1)
            self.date_from, self.date_to = end.replace(day=1), end
        elif self.period == '30days':
            self.date_from, self.date_to = today - timedelta(days=29), today

    @api.depends('company_id', 'warehouse_ids')
    def _compute_allowed_locations(self):
        for record in self:
            if not record.company_id:
                record.allowed_location_ids = False
                continue
            scope_ids = record._report_companies().ids
            scoped_env = record.with_context(allowed_company_ids=scope_ids).env
            warehouses = record.warehouse_ids or scoped_env['stock.warehouse'].with_context(active_test=False).search([('company_id', 'in', scope_ids)])
            record.allowed_location_ids = scoped_env['stock.location'].with_context(active_test=False).search([
                ('id', 'child_of', warehouses.mapped('view_location_id').ids),
                ('company_id', 'in', record._report_companies().ids), ('usage', 'in', ['view', 'internal'])])

    @api.depends('company_id', 'date_from', 'date_to', 'warehouse_ids', 'location_ids',
                 'category_ids', 'product_ids', 'lot_ids', 'uom_ids', 'own_only',
                 'group_warehouse', 'separate_variants', 'report_mode')
    def _compute_filter_summary(self):
        def names(records, empty):
            return ', '.join(records.mapped('display_name')) or empty
        for record in self:
            record.filter_summary = '\n'.join([
                f'Compañía: {record.company_id.display_name or "—"} | Fechas: {record.date_from or "—"} a {record.date_to or "—"}',
                'Almacenes: ' + names(record.warehouse_ids, 'Todos los accesibles de la compañía'),
                'Ubicaciones: ' + names(record.location_ids, 'Todas las internas de esos almacenes'),
                'Categorías: ' + names(record.category_ids, 'Todas') + ' (incluye subcategorías)',
                'Productos: ' + names(record.product_ids, 'Todos los que cumplan los filtros'),
                'Lotes / series: ' + names(record.lot_ids, 'Todos'),
                'Unidades adicionales: ' + names(record.uom_ids, 'Ninguna; se usa la unidad del producto'),
                ('Existencias propias; excluye propietarios asignados.' if record.own_only else 'Incluye existencias propias y de terceros.'),
                ('Almacenes separados.' if record.group_warehouse else 'Almacenes consolidados.') + ' ' + ('Variantes separadas.' if record.separate_variants else 'Variantes agrupadas por plantilla.'),
            ])

    @api.onchange('warehouse_ids')
    def _onchange_warehouses(self):
        self.location_ids = self.location_ids & self.allowed_location_ids

    @api.onchange('category_ids', 'product_ids')
    def _onchange_products(self):
        if self.category_ids:
            allowed = self.env['product.category'].search([('id', 'child_of', self.category_ids.ids)])
            self.product_ids = self.product_ids.filtered(lambda p: p.categ_id in allowed)
        if self.product_ids:
            self.lot_ids = self.lot_ids.filtered(lambda lot: lot.product_id in self.product_ids)
        elif self.category_ids:
            self.lot_ids = self.lot_ids.filtered(lambda lot: lot.product_id.categ_id in allowed)

    @api.onchange('company_id', 'date_from', 'date_to', 'warehouse_ids', 'location_ids',
                  'category_ids', 'product_ids', 'lot_ids', 'uom_ids', 'own_only',
                  'group_warehouse', 'group_category', 'separate_variants', 'report_mode', 'show_locations', 'show_valuation')
    def _onchange_filters(self):
        self.preview = False
        self.export_file = False
        self.export_name = False

    def action_reset_filters(self):
        self.ensure_one()
        self.check_access('write')
        today = fields.Date.context_today(self)
        self.write({'period': 'month', 'date_from': today.replace(day=1), 'date_to': today,
                    'warehouse_ids': [(5, 0, 0)], 'location_ids': [(5, 0, 0)],
                    'category_ids': [(5, 0, 0)], 'product_ids': [(5, 0, 0)],
                    'lot_ids': [(5, 0, 0)], 'uom_ids': [(5, 0, 0)],
                    'own_only': True, 'group_warehouse': True, 'group_category': True,
                    'separate_variants': True, 'report_mode': 'detail', 'show_locations': True,
                    'preview': False, 'export_file': False, 'export_name': False})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.warehouse_ids = False
        self.location_ids = False
        self.product_ids = False
        self.lot_ids = False
        self.preview = False

    def _validate_request(self):
        self.ensure_one()
        self.check_access('read')
        if self.create_uid != self.env.user:
            raise UserError(_('Este reporte pertenece a otro usuario.'))
        if self._scope_company() not in self.env.companies:
            raise UserError(_('Compañía no autorizada.'))
        if not self.date_from or not self.date_to or self.date_from > self.date_to:
            raise UserError(_('Revise el rango de fechas.'))
        scoped = self.with_context(allowed_company_ids=self._report_companies().ids)
        for records in (scoped.warehouse_ids, scoped.location_ids, scoped.product_ids, scoped.lot_ids):
            records.check_access('read')
            if any(r.company_id and r.company_id not in self._report_companies() for r in records):
                raise UserError(_('Los filtros deben pertenecer a la compañía seleccionada.'))
        self.category_ids.check_access('read')
        self.uom_ids.check_access('read')

    @staticmethod
    def _uom_root(unit):
        seen = set()
        while unit.relative_uom_id:
            if unit.id in seen:
                raise UserError(_('Hay un ciclo en las unidades de medida.'))
            seen.add(unit.id)
            unit = unit.relative_uom_id
        return unit.id

    def _scopes(self):
        warehouse_model = self.env['stock.warehouse'].with_context(active_test=False)
        warehouses = self._scope_records('warehouse_ids') or warehouse_model.search([('company_id', '=', self._scope_company().id)])
        if not warehouses:
            raise UserError(_('No hay almacenes accesibles en esta compañía.'))
        scopes = {}
        covered = set()
        for warehouse in warehouses:
            domain = [('id', 'child_of', warehouse.view_location_id.id),
                      ('usage', '=', 'internal'), ('company_id', '=', self._scope_company().id)]
            # child_of on id includes selected locations themselves.
            if self.location_ids:
                domain.append(('id', 'child_of', self._scope_records('location_ids').ids))
            locations = self.env['stock.location'].with_context(active_test=False).search(domain)
            ids = set(locations.ids)
            if covered & ids:
                raise UserError(_('Los almacenes tienen ubicaciones internas superpuestas. Revise su configuración.'))
            covered |= ids
            if ids:
                scopes[warehouse.id] = (warehouse.display_name, ids)
        if not covered:
            raise UserError(_('No hay ubicaciones internas que coincidan con los filtros.'))
        if not self.group_warehouse:
            scopes = {0: ('Consolidado de almacenes seleccionados', covered)}
        return scopes, covered

    def _report_data_single(self):
        self._validate_request()
        tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = tz.localize(datetime.combine(self.date_to + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        scopes, locations = self._scopes()
        domain = [('company_id', '=', self._scope_company().id), ('state', '=', 'done'),
                  ('date', '<', end), '|', ('location_id', 'in', list(locations)),
                  ('location_dest_id', 'in', list(locations))]
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        if self.category_ids:
            domain.append(('product_id.categ_id', 'child_of', self.category_ids.ids))
        if self.lot_ids:
            domain.append(('lot_id', 'in', self.lot_ids.ids))
        if self.own_only:
            domain.append(('owner_id', '=', False))
        lines = self.env['stock.move.line'].with_context(active_test=False).search(domain, order='date,id', limit=100001)
        if len(lines) > 100000:
            raise UserError(_('La consulta supera 100.000 líneas históricas. Filtre por productos, categorías o almacenes; no se mostrarán saldos truncados.'))
        if self.show_valuation and not self.own_only:
            raise UserError(_('Para valorar, active Excluir existencias de terceros. Puede consultar cantidades de consignación desmarcando Mostrar valoración.'))
        if self.show_valuation and len(lines) > 3000:
            raise UserError(_('La valoración supera 3.000 líneas históricas. Filtre por producto/categoría o consulte solo cantidades. No se truncará el saldo.'))
        cost_cache = {}
        def native_cost(product, at):
            key = (product.id, at)
            if key not in cost_cache:
                # Native Odoo 20 valuation includes product.value cost updates.
                # Isolate the selected company: active siblings must not sum.
                scoped = product.with_company(self._scope_company()).with_context(
                    allowed_company_ids=self._scope_company().ids, to_date=at,
                    warehouse_id=False, location=False, lot_id=False,
                    owner_id=False, from_date=False)
                cost_cache[key] = scoped.avg_cost
            return cost_cache[key]
        location_scope = {loc: scope for scope, (_, ids) in scopes.items() for loc in ids}
        events, metadata = [], {}
        opening_qty, closing_qty = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
        products_by_id = {}
        for line in lines:
            source = location_scope.get(line.location_id.id)
            destination = location_scope.get(line.location_dest_id.id)
            if source == destination:
                continue
            product = line.product_id
            entity = product if self.separate_variants else product.product_tmpl_id
            # Stored native quantity in the product's unit; no cost/valuation calls.
            quantity = line.quantity_product_uom
            unit_value = 0.0
            if self.show_valuation:
                move = line.move_id
                valued_quantity = move._get_valued_qty(signed=True)
                unit_value = movement_unit_value(move.value, valued_quantity, lambda: native_cost(product, line.date))
                products_by_id[product.id] = product
            for scope in {source, destination} - {None}:
                key = (scope, entity.id)
                metadata[key] = (scopes[scope][0], entity, product.uom_id, product.categ_id)
                events.append({'key': key, 'date': line.date, 'id': line.id,
                    'incoming': quantity if destination == scope else 0.0,
                    'outgoing': quantity if source == scope else 0.0,
                    'unit_value': unit_value,
                    'line': line})
                if self.show_valuation:
                    delta = quantity if destination == scope else -quantity
                    closing_qty[key][product.id] += delta
                    if line.date < start:
                        opening_qty[key][product.id] += delta
        balances = build_ledger(events, start, end)
        headers = ['Almacén', 'Categoría', 'Producto', 'Referencia', 'UdM']
        if self.details:
            headers += ['Fecha local', 'Documento', 'Origen', 'Tipo', 'Lote / serie']
            if self.show_locations:
                headers += ['Ubicación origen', 'Ubicación destino']
        headers += ['Saldo inicial', 'Entrada', 'Salida', 'Saldo']
        for uom in self.uom_ids:
            headers += [f'{label} ({uom.display_name})' for label in ['Inicial', 'Entrada', 'Salida', 'Saldo']]
        if self.show_valuation:
            headers += ['Moneda', 'Costo unitario movimiento', 'Valor inicial', 'Valor entrada', 'Valor salida', 'Ajuste de valoración', 'Valor saldo']
        rows = []
        monetary = {}
        if self.show_valuation:
            for key, balance in balances.items():
                initial = sum(q * native_cost(products_by_id[p], start - timedelta(microseconds=1)) for p,q in opening_qty[key].items())
                closing = sum(q * native_cost(products_by_id[p], end - timedelta(microseconds=1)) for p,q in closing_qty[key].items())
                monetary[key] = reconcile_values(balance['lines'],initial,closing,self._scope_company().currency_id.name)

        def make_row(key, quantities, event=None, label=''):
            warehouse, entity, unit, category = metadata[key]
            row = [warehouse, category.display_name, entity.display_name, entity.default_code or '', unit.display_name]
            if self.details:
                line = event['line'] if event else None
                row += [fields.Datetime.context_timestamp(self, event['date']).strftime('%Y-%m-%d %H:%M:%S') if event else '',
                        (line.picking_id.name or line.move_id.reference or '') if line else label,
                        (line.move_id.origin or '') if line else '',
                        ('Entrada' if event['incoming'] else 'Salida') if event else '',
                        (line.lot_id.name or '') if line else '']
                if self.show_locations:
                    row += [line.location_id.display_name if line else '', line.location_dest_id.display_name if line else '']
            row += list(quantities)
            for uom in self.uom_ids:
                if self._uom_root(unit) == self._uom_root(uom):
                    row += [unit._compute_quantity(q, uom, round=False) for q in quantities]
                else:
                    row += ['', '', '', '']
            if self.show_valuation:
                initial, vin, vout, adjustment, closing = monetary[key]
                if event:
                    row += event['money']
                elif label == 'SALDO INICIAL':
                    row += [self._scope_company().currency_id.name,'',initial,0.0,0.0,0.0,initial]
                elif label == 'AJUSTE DE VALORACIÓN AL CORTE':
                    row += [self._scope_company().currency_id.name,'',0.0,0.0,0.0,adjustment,closing]
                else:
                    row += [self._scope_company().currency_id.name,'',initial,vin,vout,adjustment,closing]
            return row

        def sort_key(key):
            wh, entity, unit, category = metadata[key]
            return (wh, category.display_name if self.group_category else '', entity.display_name, entity.id)

        for key in sorted(balances, key=sort_key):
            balance = balances[key]
            if self.details:
                rows.append(make_row(key, (balance['opening'], 0.0, 0.0, balance['opening']), label='SALDO INICIAL'))
                for event in balance['lines']:
                    rows.append(make_row(key, (0.0, event['incoming'], event['outgoing'], event['balance']), event))
                if self.show_valuation and abs(monetary[key][3]) > 0.000001:
                    rows.append(make_row(key,(0.0,0.0,0.0,balance['closing']),label='AJUSTE DE VALORACIÓN AL CORTE'))
                rows.append(make_row(key, (balance['opening'], balance['incoming'], balance['outgoing'], balance['closing']), label='RESUMEN DEL PRODUCTO'))
            else:
                rows.append(make_row(key, (balance['opening'], balance['incoming'], balance['outgoing'], balance['closing'])))
        title = f'Kardex físico y valorado — {self._scope_company().display_name} — {self.date_from} / {self.date_to}' if self.show_valuation else f'Kardex físico — {self._scope_company().display_name} — {self.date_from} / {self.date_to}'
        return title, headers, rows

    def _html(self, title, headers, rows):
        def cell(value):
            return escape(f'{value:,.6f}' if isinstance(value, float) else str(value or ''))
        body = ''.join('<tr>' + ''.join('<td>%s</td>' % cell(v) for v in row) + '</tr>' for row in rows)
        if not rows:
            body = '<tr><td colspan="%d">Sin movimientos que coincidan con los filtros.</td></tr>' % len(headers)
        return ('<h3>%s</h3><p>%s</p><p>Solo consulta · Cantidades en UdM indicada. Valoración: valores nativos de movimientos; '
                'saldos asignados al costo medio nativo de la compañía en cada corte. Ajuste separado para conciliar cambios de valor. '
                'Ubicaciones internas; tránsito excluido. Traslados dentro del mismo ámbito no alteran el saldo. '
                'Columnas vacías: UdM no compatible. No sumar cantidades de productos con unidades diferentes.</p>'
                '<table class="table table-sm table-striped" style="font-size:9px"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (
                escape(title), escape(self.filter_summary or '').replace('\n', '<br/>'), ''.join('<th>%s</th>' % escape(h) for h in headers), body)

    def action_preview(self):
        self.preview = self._html(*self._report_data())
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    def action_pdf(self):
        self._validate_request()
        if len(self.uom_ids) > 1:
            raise UserError(_('Para un PDF legible seleccione como máximo una unidad adicional. Excel permite todas las seleccionadas.'))
        return self.env.ref('esi_kardex_v20.action_pdf').report_action(self)

    def action_xlsx(self):
        title, headers, rows = self._report_data()
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
        sheet = book.add_worksheet('Kardex')
        filters = book.add_worksheet('Filtros aplicados')
        filters.set_column(0, 0, 110)
        for index, text in enumerate((self.filter_summary or '').splitlines()):
            filters.write(index, 0, text)
        bold = book.add_format({'bold': True, 'bg_color': '#072955', 'font_color': '#FFFFFF'})
        number = book.add_format({'num_format': '#,##0.000000'})
        sheet.write(0, 0, title)
        sheet.write(1, 0, 'Valores nativos; saldos al costo medio nativo del corte. Ajustes separados. No modifica inventario ni contabilidad.')
        sheet.write_row(3, 0, headers, bold)
        for i, row in enumerate(rows, 4):
            for j, value in enumerate(row):
                sheet.write(i, j, value, number if isinstance(value, (int, float)) else None)
        sheet.freeze_panes(4, 5)
        sheet.autofilter(3, 0, max(3, len(rows) + 3), len(headers) - 1)
        sheet.set_column(0, len(headers) - 1, 20)
        book.close()
        self.write({'export_file': BinaryBytes(output.getvalue()), 'export_name': 'ESI_Kardex.xlsx'})
        return {'type': 'ir.actions.act_url', 'url': f'/web/content/{self._name}/{self.id}/export_file/ESI_Kardex.xlsx?download=true', 'target': 'self'}


class KardexDocument(models.AbstractModel):
    _name = 'report.esi_kardex_v20.document'
    _description = 'PDF Kardex físico'

    def _get_report_values(self, docids, data=None):
        report = self.env['esi.kardex.report'].browse(docids).exists()
        report.ensure_one()
        body = report._html(*report._report_data())
        return {'docs': report, 'doc_ids': report.ids, 'doc_model': report._name, 'body': Markup(body)}
