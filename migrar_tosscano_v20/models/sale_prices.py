import json
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import file_open
from .price_mapping import resolve_prices


class SalePriceMigration(models.Model):
    _inherit = 'tosscano.migration'

    sale_price_log = fields.Text(string='Resultado de precios de venta', readonly=True, copy=False)
    retail_pricelist_id = fields.Many2one('product.pricelist', string='Lista minorista', readonly=True, copy=False)
    wholesale_pricelist_id = fields.Many2one('product.pricelist', string='Lista mayorista', readonly=True, copy=False)

    def _sale_price_source(self):
        with file_open('migrar_tosscano_v20/data/sale_prices.json', 'r') as stream:
            return json.load(stream)

    def _sale_pricelist(self, kind, label):
        key = 'sale-pricelist:' + kind
        pricelist = self._ref(key)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': '%s — %s (BOB)' % (self.root_id.name, label),
                'company_id': False, 'currency_id': self.root_id.currency_id.id,
            })
            self._bind(key, pricelist)
        if pricelist.company_id or pricelist.currency_id != self.root_id.currency_id:
            raise UserError(_('La lista %s debe ser compartida y estar en BOB.', pricelist.display_name))
        return pricelist

    def _import_sale_prices(self, data):
        self.ensure_one()
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_('Se requieren permisos de administrador de Ventas para importar precios y tarifas.'))
        source = self._sale_price_source()
        try:
            plan, missing, unused = resolve_prices(data['finished'], source)
        except ValueError as error:
            raise UserError(str(error)) from error
        # Same feature switch as native Pricelists settings, preserving other groups.
        feature = self.env.ref('product.group_product_pricelist')
        internal = self.env.ref('base.group_user')
        if feature not in internal.implied_ids:
            internal.write({'implied_ids': [(4, feature.id)]})
        retail = self._sale_pricelist('retail', 'Minorista')
        wholesale = self._sale_pricelist('wholesale', 'Mayorista')
        notes, updated, skipped = [], 0, 0
        for row in plan:
            source_product = next(p for p in data['finished'] if p['key'] == row['key'])
            conflict = self._finished_conflict(source_product)
            if conflict:
                notes.append(conflict)
                continue
            template = self._ref(row['key'])
            if not template:
                notes.append('Sin producto importado: ' + row['code'])
                continue
            if template.company_id:
                notes.append('Precio pendiente: producto no compartido ' + row['code'])
                continue
            revision = 'sale-price:%s:%s:%s:%s' % (source['revision'], template.id, row['retail'], row['wholesale'])
            if self._ref(revision):
                skipped += 1
                continue
            template.write({'list_price': row['retail']})
            for kind, pricelist in [('retail', retail), ('wholesale', wholesale)]:
                key = 'sale-rule:%s:%s' % (kind, template.id)
                rule = self._ref(key)
                values = {'pricelist_id': pricelist.id, 'product_tmpl_id': template.id,
                          'product_id': False, 'categ_id': False, 'min_quantity': 0,
                          'compute_price': 'fixed', 'fixed_price': row[kind],
                          'date_start': False, 'date_end': False, 'uom_id': False}
                if rule:
                    if rule.pricelist_id != pricelist or rule.product_tmpl_id != template:
                        raise UserError(_('Una regla importada fue reasignada. Revise la tarifa de %s.', row['code']))
                    rule.write(values)
                else:
                    rule = self.env['product.pricelist.item'].create(values)
                    self._bind(key, rule)
            self._bind(revision, template)
            updated += 1
        notes.insert(0, '%s plantillas actualizadas; %s ya procesadas. Precios por par para todas sus tallas.' % (updated, skipped))
        notes.append('Tarifas en BOB compartidas entre sucursales. Seleccione Minorista o Mayorista en la cotización o en el cliente. No se inventó una cantidad mínima mayorista.')
        fallback = [r['code'] for r in plan if r['wholesale_fallback']]
        if fallback:
            notes.append('Sin importe mayorista en Excel; se utiliza el minorista: ' + ', '.join(fallback))
        for row in source['rows']:
            if row['wholesale'] is not None and row['wholesale'] > row['retail']:
                notes.append('Importe conservado del Excel: %s minorista %s / mayorista %s.' % (row['code'], row['retail'], row['wholesale']))
        if missing:
            notes.append('Sin correspondencia de precio: ' + ', '.join(missing))
        if unused:
            notes.append('Modelos del Excel sin plantilla en el catálogo importado: ' + ', '.join(unused))
        notes.append('La columna Costo de producción del Excel es solo evidencia: no modifica costos, AVCO ni valoración. No se modificaron impuestos, pedidos, clientes o configuraciones POS existentes.')
        self.write({'retail_pricelist_id': retail.id, 'wholesale_pricelist_id': wholesale.id,
                    'sale_price_log': '\n'.join(notes)})
        return notes

    def action_import_sale_prices(self):
        self._lock()
        if not self.data_imported:
            raise UserError(_('Primero pulse 1. Importar datos.'))
        notes = self._import_sale_prices(self._source())
        self.import_log = (self.import_log or '') + '\n\nPRECIOS DE VENTA\n' + '\n'.join(notes)
        return True
