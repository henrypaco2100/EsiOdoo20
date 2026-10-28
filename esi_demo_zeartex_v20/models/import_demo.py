# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

CASES = [
    ('IMP-001', 'China - Arica - Santa Cruz', 'sea', 'CN', 10000, [
        ('Flete marítimo', 'FLETE_MAR', 1200, 'by_volume', True),
        ('Seguro internacional', 'SEGURO_INT', 150, 'by_current_cost_price', True),
        ('Manipulación portuaria', 'MANIP_PUERTO', 300, 'by_volume', True),
        ('Arancel supuesto DEMO', 'ARANCEL_DEMO', 1000, 'by_current_cost_price', True),
        ('Despachante', 'DESP_ADUANA', 250, 'by_current_cost_price', True),
        ('Transporte a almacén', 'FLETE_TERR', 800, 'by_weight', True),
        ('IVA recuperable ilustrativo', 'IVA_REC_DEMO', 1100, 'equal', False)]),
    ('IMP-002', 'China - Viru Viru - Santa Cruz', 'air', 'CN', 3800, [
        ('Flete aéreo', 'FLETE_AEREO', 820, 'by_weight', True),
        ('Seguro internacional', 'SEGURO_INT', 60, 'by_current_cost_price', True),
        ('Manipulación aeroportuaria', 'MANIP_AEREO', 120, 'by_quantity', True),
        ('Arancel supuesto DEMO', 'ARANCEL_DEMO', 400, 'by_current_cost_price', True),
        ('IVA recuperable ilustrativo', 'IVA_REC_DEMO', 430, 'equal', False)]),
    ('IMP-003', 'Brasil - Santa Cruz', 'road', 'BR', 6500, [
        ('Flete terrestre', 'FLETE_TERR', 680, 'by_weight', True),
        ('Seguro', 'SEGURO_INT', 85, 'by_current_cost_price', True),
        ('Despachante', 'DESP_ADUANA', 200, 'by_current_cost_price', True),
        ('Arancel supuesto DEMO', 'ARANCEL_DEMO', 440, 'by_current_cost_price', True),
        ('IVA recuperable ilustrativo', 'IVA_REC_DEMO', 720, 'equal', False)]),
    ('IMP-004', 'Corredor ferroviario internacional (ruta ilustrativa)', 'rail', 'BR', 4500, [
        ('Flete ferroviario', 'FLETE_FERRO', 400, 'by_weight', True),
        ('Transbordo', 'TRANSBORDO', 120, 'by_quantity', True),
        ('Flete terrestre final', 'FLETE_TERR', 260, 'by_weight', True),
        ('Seguro', 'SEGURO_INT', 55, 'by_current_cost_price', True),
        ('Arancel supuesto DEMO', 'ARANCEL_DEMO', 330, 'by_current_cost_price', True),
        ('IVA recuperable ilustrativo', 'IVA_REC_DEMO', 500, 'equal', False)]),
]


class EsiZeartexDemoImports(models.Model):
    _inherit = 'esi.zeartex.demo'

    def action_check_avco(self):
        self.ensure_one()
        company = self._company()
        Cat = self.env['product.category'].sudo().with_company(company)
        Product = self.env['product.template'].sudo().with_company(company)
        templates = Product.search([('esi_zeartex_code', '=like', 'ZEA-%'), ('company_id', '=', company.id)])
        if not templates:
            raise UserError(_('Primero cargue el catálogo de Zeartex.'))
        categories = templates.mapped('categ_id')
        Quant = self.env['stock.quant'].sudo().with_company(company)
        Move = self.env['stock.move'].sudo().with_company(company)
        protected = []
        updated = []
        for cat in categories:
            if cat.property_cost_method == 'average':
                continue
            products = Product.search([('categ_id', '=', cat.id)])
            if any(not p.esi_zeartex_code or p.company_id != company for p in products):
                protected.append('%s (categoría compartida)' % cat.display_name)
                continue
            variants = products.mapped('product_variant_ids')
            if Quant.search_count([('product_id', 'in', variants.ids), ('quantity', '!=', 0)]):
                protected.append('%s (existencias)' % cat.display_name)
                continue
            if Move.search_count([('product_id', 'in', variants.ids), ('state', '=', 'done')]):
                protected.append('%s (movimientos anteriores)' % cat.display_name)
                continue
            cat.write({'property_cost_method': 'average'})
            updated.append(cat.display_name)
        msg = 'Categorías cambiadas a AVCO: %s. Pendientes de revisión manual: %s.' % (
            len(updated), ', '.join(protected) or 'ninguna')
        return self._notify(msg)

    def action_create_import_scenarios(self):
        self.ensure_one()
        company = self._company()
        if company.currency_id.name != 'BOB':
            raise UserError(_('La compañía debe usar BOB para esta demostración.'))
        root = self.env['product.category'].sudo().search([
            ('name', '=', 'ZEARTEX | COTILLÓN E IMPORTACIONES')], limit=1)
        if not root:
            raise UserError(_('Primero ejecute 1. Cargar catálogo.'))
        dollar = self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)
        if not dollar:
            raise UserError(_('No existe USD en Odoo.'))
        # Solo gastos ficticios, no creamos cuentas ni impuestos oficiales.
        service_model = self.env['product.template'].sudo().with_company(company)
        scenario_model = self.env['esi.zeartex.import'].sudo().with_company(company)
        countries = self.env['res.country'].sudo()
        created = 0
        variants = self.env['product.product'].sudo().with_company(company).search([
            ('product_tmpl_id.esi_zeartex_code', '=like', 'ZEA-%'),
            ('product_tmpl_id.company_id', '=', company.id)], limit=24)
        supplier = self.env['res.partner'].sudo().search([('ref', '=', 'ZEA-PROV-01')], limit=1)
        Purchase = self.env['purchase.order'].sudo().with_company(company)
        for code, route_name, route, country, goods, expenses in CASES:
            existing = scenario_model.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
            if existing:
                continue
            expense_commands = []
            for title, ref, amount, method, capitalizable in expenses:
                if capitalizable:
                    product_code = 'ZEA-GASTO-' + ref
                    item = service_model.search([('default_code', '=', product_code), ('company_id', '=', company.id)], limit=1)
                    if not item:
                        vals = {'name': 'ZEARTEX DEMO - ' + title, 'default_code': product_code,
                                'type': 'service', 'company_id': company.id,
                                'sale_ok': False, 'purchase_ok': True, 'categ_id': root.id,
                                'landed_cost_ok': True}
                        if 'split_method_landed_cost' in service_model._fields:
                            vals['split_method_landed_cost'] = method
                        item = service_model.create(vals)
                expense_commands.append((0, 0, {'name': title, 'service_code': 'ZEA-GASTO-' + ref,
                    'amount_usd': amount, 'split_method': method, 'capitalizable': capitalizable}))
            purchase = Purchase.search([('origin', '=', 'ZEA-' + code),
                ('company_id', '=', company.id)], limit=1)
            if not purchase and supplier and variants:
                product = variants[(created * 5) % len(variants)]
                po_line = {'product_id': product.id, 'product_qty': 200 + created * 60,
                           'name': product.display_name,
                           'price_unit': round(float(product.standard_price) / 6.96, 2),
                           'taxes_id': [(5, 0, 0)]}
                if 'uom_id' in self.env['purchase.order.line']._fields:
                    po_line['uom_id'] = product.uom_id.id
                purchase = Purchase.create({'partner_id': supplier.id, 'company_id': company.id,
                    'currency_id': dollar.id, 'origin': 'ZEA-' + code,
                    'order_line': [(0, 0, po_line)]})
            scenario_model.create({'name': route_name, 'code': code,
                'company_id': company.id, 'origin_country_id': countries.search([('code', '=', country)], limit=1).id,
                'currency_id': dollar.id, 'goods_usd': goods, 'route': route,
                'purchase_id': purchase.id if purchase else False,
                'line_ids': expense_commands})
            created += 1
        return self._notify(_('Expedientes creados: %s. No se validaron inventarios, costos ni asientos.') % created)
