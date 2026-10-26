# -*- coding: utf-8 -*-
import json
from pathlib import Path
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.binary import BinaryBytes

ROOT = Path(__file__).resolve().parent.parent


class EsiZeartexProduct(models.Model):
    _inherit = 'product.template'
    esi_zeartex_code = fields.Char(string='Código DEMO Zeartex', index=True, copy=False)


class EsiZeartexDemo(models.Model):
    _name = 'esi.zeartex.demo'
    _description = 'Asistente de carga DEMO Zeartex'

    name = fields.Char(default='Importadora Zeartex SRL - DEMO', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    product_count = fields.Integer(compute='_compute_counts')
    supplier_count = fields.Integer(compute='_compute_counts')
    customer_count = fields.Integer(compute='_compute_counts')

    def _compute_counts(self):
        for rec in self:
            rec.product_count = rec.env['product.template'].sudo().search_count([('esi_zeartex_code', '=like', 'ZEA-%')])
            rec.supplier_count = rec.env['res.partner'].sudo().search_count([('ref', '=like', 'ZEA-PROV-%')])
            rec.customer_count = rec.env['res.partner'].sudo().search_count([('ref', '=like', 'ZEA-CLI-%')])

    def _company(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo administradores pueden cargar la demostración.'))
        company = self.company_id
        if company not in self.env.user.company_ids:
            raise UserError(_('La compañía seleccionada no está habilitada para este usuario.'))
        return company

    def _notify(self, message):
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': 'ESI Demo Zeartex', 'message': message, 'type': 'success', 'sticky': False}}

    def _category(self, name, parent=False):
        Cat = self.env['product.category'].sudo()
        dom = [('name', '=', name), ('parent_id', '=', parent.id if parent else False)]
        cat = Cat.search(dom, limit=1)
        return cat or Cat.create({'name': name, 'parent_id': parent.id if parent else False})

    def _attribute(self):
        Attr = self.env['product.attribute'].sudo()
        attr = Attr.search([('name', '=', 'Color Zeartex DEMO')], limit=1)
        if not attr:
            attr = Attr.create({'name': 'Color Zeartex DEMO', 'create_variant': 'always', 'display_type': 'radio'})
        return attr

    def _pricelists(self, company):
        Currency = self.env['res.currency'].sudo()
        bob = Currency.search([('name', '=', 'BOB')], limit=1)
        if not bob:
            raise UserError(_('No existe moneda BOB. Revise Ajustes > Monedas.'))
        if company.currency_id != bob:
            raise UserError(_('La compañía actual no tiene BOB como moneda. Para evitar precios equivocados no se cargan tarifas. Seleccione una compañía BOB o ajuste una estrategia de moneda con su contador.'))
        Price = self.env['product.pricelist'].sudo().with_company(company)
        result = {}
        for key, label in [('retail','Zeartex Minorista - DEMO'), ('wholesale','Zeartex Mayorista - DEMO')]:
            p = Price.search([('name', '=', label), ('company_id', '=', company.id)], limit=1)
            if not p:
                vals = {'name': label, 'currency_id': bob.id, 'company_id': company.id}
                p = Price.create(vals)
            result[key] = p
        return result

    def _contacts(self, company):
        Partner = self.env['res.partner'].sudo().with_company(company)
        suppliers = [
            ('Shenzhen Fiesta Export Ltd.', 'CN'), ('Guangzhou Colorful Trading Co.', 'CN'),
            ('Yiwu Celebration Goods Co.', 'CN'), ('Lima Party Wholesale SAC', 'PE'),
            ('São Paulo Embalagens Ltda.', 'BR'), ('Distribuidora Nacional Oriente SRL', 'BO'),
            ('Plásticos Altiplano SRL', 'BO'), ('Empaques del Valle SRL', 'BO'),
        ]
        customers = [
            'Distribuidora Fiesta Mayorista SRL','Cotillón La Estrella','Comercial Sol Naciente','Distribuidora Arcoíris','Comercial Burbujas',
            'Fiestas Bolivia','Cotillón El Carnaval','Distribuidora Altiplano','Mayorista El Globo','Comercial Mil Colores',
            'Fiesta Express SRL','Distribuidora La Paz','Cotillón Oriente','Distribuidora El Regalito','Comercial Primavera',
            'María Gómez (DEMO)','Carlos Flores (DEMO)','Laura Suárez (DEMO)','José Rojas (DEMO)','Andrea Salinas (DEMO)',
            'Paola Medina (DEMO)','Fernando Vargas (DEMO)','Gabriela Cruz (DEMO)','Diego Arias (DEMO)','Lucía Herrera (DEMO)'
        ]
        res_sup = []
        res_cus = []
        for i, (name, cc) in enumerate(suppliers, 1):
            ref = 'ZEA-PROV-%02d' % i
            partner = Partner.search([('ref', '=', ref)], limit=1)
            if not partner:
                country = self.env['res.country'].sudo().search([('code', '=', cc)], limit=1)
                partner = Partner.create({'name': name, 'ref': ref, 'is_company': True, 'country_id': country.id or False, 'supplier_rank': 1})
            res_sup.append(partner)
        for i, name in enumerate(customers, 1):
            ref = 'ZEA-CLI-%02d' % i
            partner = Partner.search([('ref', '=', ref)], limit=1)
            if not partner:
                partner = Partner.create({'name': name, 'ref': ref, 'is_company': i <= 15, 'customer_rank': 1})
            res_cus.append(partner)
        return res_sup, res_cus

    def action_load_catalog(self):
        self.ensure_one()
        company = self._company()
        # Require BOB before any writes. Avoid converting fictitious Bs into USD.
        pl = self._pricelists(company)
        with self.env.cr.savepoint():
            suppliers, customers = self._contacts(company)
            root = self._category('ZEARTEX | COTILLÓN E IMPORTACIONES')
            attr = self._attribute()
            Template = self.env['product.template'].sudo().with_company(company)
            AVal = self.env['product.attribute.value'].sudo()
            Priceline = self.env['product.pricelist.item'].sudo().with_company(company)
            data = json.loads((ROOT / 'data/catalogo.json').read_text(encoding='utf-8'))
            for idx, item in enumerate(data):
                parent = self._category(item['family'], root)
                category = self._category(item['subcategory'], parent)
                product = Template.search([('esi_zeartex_code', '=', item['code']), ('company_id', '=', company.id)], limit=1)
                if not product:
                    values = {
                        'name': item['name'], 'esi_zeartex_code': item['code'], 'default_code': item['code'],
                        'type': 'consu', 'is_storable': True,
                        'sale_ok': True, 'purchase_ok': True,
                        'company_id': company.id, 'categ_id': category.id,
                        'list_price': item['retail'], 'standard_price': item['cost'],
                        'description_sale': 'ZEARTEX DEMO. Artículo ilustrativo para ventas mayoristas y minoristas.',
                    }
                    img = ROOT / 'static' / item['photo']
                    if img.exists():
                        values['image_1920'] = BinaryBytes(img.read_bytes(), filename=img.name)
                    if item['colors']:
                        vals=[]
                        for color in item['colors']:
                            av=AVal.search([('attribute_id','=',attr.id),('name','=',color)],limit=1)
                            if not av: av=AVal.create({'attribute_id':attr.id,'name':color})
                            vals.append(av.id)
                        values['attribute_line_ids'] = [(0, 0, {'attribute_id': attr.id, 'value_ids': [(6,0,vals)]})]
                    product = Template.create(values)
                    if item['colors']:
                        # Variant codes are distinct and traceable.
                        for variant in product.product_variant_ids:
                            color = variant.product_template_attribute_value_ids.mapped('name')
                            variant.default_code = item['code'] + '-' + (color[0][:3].upper() if color else 'VAR')
                for typ, field in [('retail','retail'), ('wholesale','wholesale')]:
                    existing = Priceline.search([('pricelist_id','=',pl[typ].id),('product_tmpl_id','=',product.id)],limit=1)
                    if not existing:
                        Priceline.create({'pricelist_id':pl[typ].id,'applied_on':'1_product','product_tmpl_id':product.id,'compute_price':'fixed','fixed_price':item[field]})
                # One vendor for the demo, with no fictitious promises on lead times.
                Supp = self.env['product.supplierinfo'].sudo()
                if not Supp.search([('product_tmpl_id','=',product.id)],limit=1):
                    Supp.create({'partner_id': suppliers[idx % len(suppliers)].id,
                                 'product_tmpl_id':product.id, 'price':item['cost'],
                                 'min_qty':1, 'currency_id':company.currency_id.id})
                # Limit POS products to dedicated categories; standard POS uses product catalog.
                if 'available_in_pos' in product._fields:
                    product.write({'available_in_pos': True})
                if 'pos_categ_ids' in product._fields:
                    PosCat=self.env['pos.category'].sudo()
                    cat=PosCat.search([('name','=',item['family'])],limit=1)
                    if not cat:cat=PosCat.create({'name':item['family']})
                    product.write({'pos_categ_ids':[(4,cat.id)]})
        return self._notify('Catálogo cargado: 150 productos base, variantes, 8 proveedores y 25 clientes. Inventario intacto.')

    def action_create_drafts(self):
        self.ensure_one()
        company=self._company()
        templates=self.env['product.template'].sudo().with_company(company)
        products=templates.search([('esi_zeartex_code','=like','ZEA-%'),('company_id','=',company.id)],limit=12)
        if len(products)<8:
            raise UserError(_('Primero cargue el catálogo de productos.'))
        suppliers=self.env['res.partner'].sudo().search([('ref','=like','ZEA-PROV-%')],limit=5)
        clients=self.env['res.partner'].sudo().search([('ref','=like','ZEA-CLI-%')],limit=10)
        if not suppliers or not clients:raise UserError(_('Faltan clientes o proveedores Zeartex.'))
        Purchase=self.env['purchase.order'].sudo().with_company(company)
        Sale=self.env['sale.order'].sudo().with_company(company)
        for i,partner in enumerate(suppliers):
            origin='ZEA-DEMO-COMPRA-%02d' % (i+1)
            if not Purchase.search([('origin','=',origin),('company_id','=',company.id)],limit=1):
                p=products[i % len(products)].product_variant_ids[:1]
                Purchase.create({'partner_id':partner.id,'company_id':company.id,'origin':origin,
                                 'order_line':[(0,0,{'product_id':p.id,'name':p.display_name,'product_qty':10+i*3,'price_unit':float(products[i%len(products)].standard_price)})]})
        for i,partner in enumerate(clients):
            origin='ZEA-DEMO-VENTA-%02d' % (i+1)
            if not Sale.search([('origin','=',origin),('company_id','=',company.id)],limit=1):
                p=products[(i+2)%len(products)].product_variant_ids[:1]
                Sale.create({'partner_id':partner.id,'company_id':company.id,'origin':origin,
                             'order_line':[(0,0,{'product_id':p.id,'name':p.display_name,'product_uom_qty':2+i%5,'price_unit':float(products[(i+2)%len(products)].list_price)})]})
        return self._notify('Se crearon documentos de ejemplo solamente en borrador. No se confirmaron compras, ventas ni facturas.')

    def action_create_pos(self):
        self.ensure_one()
        company=self._company()
        POS=self.env['pos.config'].sudo().with_company(company)
        name='Zeartex - Tienda (DEMO)'
        existing=POS.search([('name','=',name),('company_id','=',company.id)],limit=1)
        if existing:return self._notify('El Punto de Venta Zeartex ya existe; no se duplicó.')
        # POS may require company-specific payment methods and sale journal.
        method=self.env['pos.payment.method'].sudo().search([('company_id','=',company.id)],limit=1)
        if not method:
            raise UserError(_('Para crear el POS Zeartex necesita al menos un método de pago configurado para esta compañía. Configure primero los diarios y métodos de pago en Punto de Venta.'))
        vals={'name':name,'company_id':company.id,'payment_method_ids':[(6,0,method.ids)]}
        if 'module_pos_restaurant' in POS._fields: vals['module_pos_restaurant']=False
        POS.create(vals)
        return self._notify('POS Zeartex creado sin iniciar sesiones. Revise los métodos de pago antes de abrir caja.')

    def action_load_stock(self):
        """Optional real inventory adjustment. NEVER run automatically on install."""
        self.ensure_one()
        company = self._company()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Se requieren permisos de Administrador de Inventario.'))
        warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('No hay almacén interno configurado para esta compañía.'))
        location = warehouse.lot_stock_id
        Quant = self.env['stock.quant'].sudo().with_company(company).with_context(inventory_mode=True)
        products = self.env['product.template'].sudo().with_company(company).search([
            ('esi_zeartex_code', '=like', 'ZEA-%'), ('company_id', '=', company.id)])
        if len(products) != 150:
            raise UserError(_('Primero cargue los 150 productos base de Zeartex.'))
        data = {p['code']: p for p in json.loads((ROOT / 'data/catalogo.json').read_text(encoding='utf-8'))}
        changed = 0
        with self.env.cr.savepoint():
            for template in products:
                item = data.get(template.esi_zeartex_code)
                if not item:
                    continue
                variants = template.product_variant_ids
                for variant in variants:
                    desired = float(item['initial_qty'])
                    # Split quantities across variants, rather than multiplying stock by the number of colors.
                    if len(variants) > 1:
                        desired = float(item['initial_qty'] // len(variants))
                    quant = Quant.search([('product_id', '=', variant.id),
                        ('location_id', '=', location.id), ('lot_id', '=', False),
                        ('package_id', '=', False), ('owner_id', '=', False)], limit=1)
                    if quant and quant.quantity:
                        # Never overwrite stock of a product that was already used.
                        continue
                    if not quant:
                        quant = Quant.create({'product_id': variant.id, 'location_id': location.id})
                    quant.inventory_quantity = desired
                    result = quant.action_apply_inventory()
                    if isinstance(result, dict):
                        raise UserError(_('Conflicto de inventario para %s. No se modificó la carga.') % variant.display_name)
                    changed += 1
        return self._notify(_('Inventario de prueba registrado en %s referencias. No se alteraron existencias previas.') % changed)
