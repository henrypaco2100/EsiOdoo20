import hashlib
import json
from collections import defaultdict
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import file_open


class DirectMigration(models.Model):
    _inherit = 'tosscano.migration'

    data_imported = fields.Boolean(readonly=True, copy=False)
    stock_imported = fields.Boolean(readonly=True, copy=False)
    import_log = fields.Text(string='Resultado de importación', readonly=True, copy=False)
    valuation_pending_log = fields.Text(string='Saldos cargados sin costo de apertura', readonly=True, copy=False)
    product_count = fields.Integer(string='Productos/variantes vinculados', readonly=True, copy=False)

    def _source(self):
        with file_open('migrar_tosscano_v20/data/direct.json', 'r') as stream:
            return json.load(stream)

    def _lock(self):
        self._check_scope()
        required = {'esi_material_type', 'esi_measure', 'esi_component_ok', 'esi_manufacture_ok'}
        if required - set(self.env['product.template']._fields):
            raise UserError(_('Actualice primero esi_calzados_v20 a la versión 20.0.11.2.0 o posterior.'))
        if any(c.currency_id.name != 'BOB' for c in (self.root_id | self.factory_id | self.cbba_id | self.scz_id)):
            raise UserError(_('Los costos de origen están en bolivianos. Las compañías seleccionadas deben usar BOB.'))
        self.env.cr.execute('SELECT pg_advisory_xact_lock(20261023, 27102026)')
        self.invalidate_recordset()

    def _xmlname(self, key):
        # Stable across repeated runs/configurations; company scope is explicit.
        scope = '%s:%s:%s' % (self.root_id.id, self.factory_id.id, key)
        return 'import_' + hashlib.sha256(scope.encode()).hexdigest()

    def _ref(self, key):
        return self.env.ref('tosscano_import_data.' + self._xmlname(key), raise_if_not_found=False)

    def _bind(self, key, record):
        self.env['ir.model.data'].create({'module': 'tosscano_import_data',
            'name': self._xmlname(key), 'model': record._name, 'res_id': record.id, 'noupdate': True})
        return record

    def _category(self, family, subfamily=None):
        parent = False
        for name in [family, subfamily]:
            if not name:
                continue
            name = ' '.join(name.upper().split())
            found = self.env['product.category'].search([('name', '=', name), ('parent_id', '=', parent.id if parent else False)])
            if len(found) > 1:
                raise UserError(_('Categorías duplicadas con el mismo padre: %s', name))
            parent = found or self.env['product.category'].create({'name': name, 'parent_id': parent.id if parent else False})
        return parent

    def _uom(self, label):
        label = {'UNI': 'UNIDAD', 'UNIDADES': 'UNIDAD', 'METROS': 'METRO', 'M': 'METRO', 'FT2': 'PIE2', 'L': 'LITRO', 'GR': 'GRAMO'}.get(label.upper(), label.upper())
        native = {'UNIDAD': 'product_uom_unit', 'METRO': 'product_uom_meter', 'LITRO': 'product_uom_litre', 'KG': 'product_uom_kgm', 'GRAMO': 'product_uom_gram', 'M2': 'product_uom_square_meter'}
        if label in native:
            result = self.env.ref('uom.' + native[label])
            if not result.active:
                result.active = True
            return result
        result = self._ref('uom:' + label)
        if result:
            return result
        found = self.env['uom.uom'].search([('name', '=', label), ('relative_uom_id', '=', False)])
        if len(found) > 1:
            raise UserError(_('Unidad duplicada: %s', label))
        vals = {'name': label, 'relative_factor': 1.0}
        if label == 'PIE2':
            vals.update(relative_uom_id=self._uom('M2').id, relative_factor=0.09290304)
            found = self.env['uom.uom']
        # PAR, ROLLO, CONO, BOTE, LATA, PAQUETE remain independent units.
        # A pair represents one pair of shoes, not two inventory pairs.
        return self._bind('uom:' + label, found or self.env['uom.uom'].create(vals))

    def _attribute(self, name, grouped=False):
        attr = self.env['product.attribute'].search([('name', '=', name)], limit=2)
        if len(attr) > 1:
            raise UserError(_('Atributo duplicado: %s', name))
        if not attr:
            attr = self.env['product.attribute'].create({'name': name, 'create_variant': 'always', 'esi_group_production': grouped})
        if attr.create_variant != 'always':
            raise UserError(_('El atributo %s existente no crea variantes automáticamente. Cambie su configuración antes de continuar.', name))
        if grouped and not attr.esi_group_production:
            attr.esi_group_production = True
        return attr

    def _attribute_line(self, name, values, grouped=False):
        attr = self._attribute(name, grouped)
        ids = []
        for name_value in values:
            value = self.env['product.attribute.value'].search([('attribute_id', '=', attr.id), ('name', '=', str(name_value))], limit=2)
            if len(value) > 1:
                raise UserError(_('Valor de atributo duplicado: %s', name_value))
            value = value or self.env['product.attribute.value'].create({'attribute_id': attr.id, 'name': str(name_value)})
            ids.append(value.id)
        return (0, 0, {'attribute_id': attr.id, 'value_ids': [(6, 0, ids)]})

    def _material(self, row):
        product = self._ref(row['key'])
        if product:
            return product
        company = self.factory_id
        uom = self._uom(row['uom'])
        existing = self.env['product.product'].with_context(active_test=False).search([('default_code', '=', row['code']), ('company_id', '=', company.id)])
        if existing:
            if len(existing) != 1 or existing.uom_id != uom or not existing.is_storable:
                raise UserError(_('Código existente incompatible: %s', row['code']))
            # Reuse without rewriting costs, names or categories of existing stock.
            return self._bind(row['key'], existing)
        template = self.env['product.template'].with_company(company).create({
            'name': row['name'], 'default_code': row['code'], 'type': 'consu', 'is_storable': True,
            'company_id': company.id, 'uom_id': uom.id, 'categ_id': self._category(row.get('family') or 'MATERIAS PRIMAS', row.get('subfamily') or 'OTROS MATERIALES').id,
            'purchase_ok': True, 'sale_ok': False, 'esi_component_ok': row.get('family') != 'HERRAMIENTAS',
            'esi_manufacture_ok': False, 'esi_measure': str(row.get('measure') or ''), 'esi_material_type': str(row.get('type') or ''),
            'standard_price': float(row.get('cost') or 0),
        })
        return self._bind(row['key'], template.product_variant_id)

    def _finished(self, row):
        template = self._ref(row['key'])
        if not template:
            if self.env['product.product'].with_context(active_test=False).search_count([('default_code', '=like', row['code'] + '-T%')]):
                raise UserError(_('Ya existen referencias de tallas del código %s sin vínculo con esta migración.', row['code']))
            lines = [self._attribute_line('Talla', row['sizes'], True), self._attribute_line('Modelo', [row['subfamily']])]
            title = ' '.join(row['name'].upper().split())
            if 'CON FORRO' in title or 'SIN FORRO' in title:
                lines.append(self._attribute_line('Forro', ['Con forro' if 'CON FORRO' in title else 'Sin forro']))
            if 'CHAROL' in title or 'LUSTRABLE' in title:
                lines.append(self._attribute_line('Acabado', ['Charol' if 'CHAROL' in title else 'Lustrable']))
            if 'CUERO' in title or 'LONA' in title:
                lines.append(self._attribute_line('Material', ['Cuero' if 'CUERO' in title else 'Lona']))
            if row.get('color'):
                lines.append(self._attribute_line('Color', [row['color']]))
            template = self.env['product.template'].create({
                'name': row['name'].strip(), 'type': 'consu', 'is_storable': True, 'company_id': False,
                'uom_id': self._uom('PAR').id, 'categ_id': self._category('CALZADOS ' + row['family'], row['subfamily']).id,
                'sale_ok': True, 'purchase_ok': False, 'esi_manufacture_ok': True, 'esi_component_ok': False,
                'attribute_line_ids': lines,
            })
            self._bind(row['key'], template)
        for product in template.product_variant_ids:
            size = product.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id.name == 'Talla').name
            key = row['key'] + ':' + size
            if not self._ref(key):
                product.default_code = row['code'] + '-T' + size
                self._bind(key, product)
        return template

    def _accounts(self, rows, notes):
        pending = list(rows)
        while pending:
            progress = False
            for r in pending[:]:
                if r.get('parent') and not self._ref('account:' + r['parent']):
                    continue
                key = 'account:' + r['id']
                if not self._ref(key):
                    model = self.env['account.account'].with_company(self.root_id).with_context(active_test=False)
                    found = model.search([('code', '=', str(r['code'])), ('company_ids', 'in', self.root_id.ids)])
                    if found:
                        if len(found) != 1 or found.account_type != r['type']:
                            notes.append('Cuenta existente incompatible, no modificada: '+str(r['code']))
                            pending.remove(r)
                            progress=True
                            continue
                        account=found
                    else:
                        parent = self._ref('account:' + r['parent']) if r.get('parent') else False
                        account = model.create({'code': str(r['code']), 'name': r['name'], 'account_type': r['type'],
                            'active': bool(r['active']), 'reconcile': bool(r['reconcile']) or r['type'] in ('asset_receivable', 'liability_payable'),
                            'company_ids': [(6, 0, self.root_id.ids)], 'parent_id': parent.id if parent else False,
                            'description': r.get('description') or False, 'note': r.get('note') or False})
                    self._bind(key, account)
                pending.remove(r)
                progress = True
            if not progress:
                notes.extend('Cuenta pendiente por padre no disponible: '+str(r['code']) for r in pending)
                break

    def action_import_data(self):
        self._lock()
        data = self._source()
        notes = list(data['notes'])
        if not self.env.user.has_group('account.group_account_manager') or not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('La importación requiere permisos de administrador de Contabilidad e Inventario.'))
        for unit in data['units']:
            self._uom(unit)
        for row in data['materials']:
            self._material(row)
        for row in data['finished']:
            self._finished(row)
        self._accounts(data['accounts'], notes)
        self._configure_category_accounting()
        self._recipes(data, notes)
        self.write({'data_imported': True, 'loaded': True,
                    'product_count': len(data['materials']) + sum(len(r['sizes']) for r in data['finished']),
                    'import_log': '\n'.join(['DATOS IMPORTADOS', 'Categorías: familia → subfamilia.',
                    'Unidades: '+', '.join(data['units']),
                    '%s materias primas; %s plantillas de calzado.' % (len(data['materials']), len(data['finished'])),
                    'Terminados obtenidos de las hojas de existencias; no del archivo de recetas duplicado.',
                    'Modelos separados por código/color; variantes Talla y Color. Las descripciones originales se conservan.',
                    'No hay costos de apertura de terminados: complete su costo en cada sucursal antes de importar esos saldos.'] + notes)})
        return True

    def _recipes(self, data, notes):
        # A recipe is created only when every positive component is unambiguous
        # and has the same inventory unit. Never silently truncate a recipe.
        by_code = defaultdict(list)
        for row in data['materials']:
            by_code[row['code']].append(self._ref(row['key']))
        for recipe in data['recipes']:
            components = [r for r in data['components'] if r['recipe'] == recipe['code'] and r['qty_per_pair'] > 0]
            lines=[]
            errors=[]
            for r in components:
                products=list({p.id:p for p in by_code.get(r['code'], [])}.values())
                if len(products)!=1:
                    errors.append(str(r['code'] or r['name'])+' sin correspondencia única')
                    continue
                product=products[0]
                uom=self._uom(r['uom'])
                if uom!=product.uom_id or not product.esi_component_ok:
                    errors.append(str(r['code'])+' unidad o uso pendiente')
                    continue
                if r['code'] in ('ACC-PLA-40','ACC-ETQ-LEN-MIL-40','ACC-BOL-CEL-35'):
                    errors.append(str(r['code'])+' requiere distribución por talla o concepto')
                    continue
                lines.append((0,0,{'product_id':product.id,'product_qty':r['qty_per_pair'],'uom_id':uom.id}))
            if errors:
                notes.append('LdM '+recipe['code']+' no creada: '+', '.join(sorted(set(errors))))
                continue
            for row in data['finished']:
                if not row['code'].startswith(recipe['code']+'-'):
                    continue
                key='bom:'+row['key']
                if self._ref(key):continue
                template=self._ref(row['key'])
                bom=self.env['mrp.bom'].with_company(self.factory_id).create({
                    'product_tmpl_id':template.id,'company_id':self.factory_id.id,'product_qty':1,
                    'uom_id':template.uom_id.id,'type':'normal','code':recipe['code'],
                    'esi_multi_variant':True,'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)],
                    'bom_line_ids':lines})
                self._bind(key,bom)

    def action_import_stock(self):
        self._lock()
        if not self.data_imported:
            raise UserError(_('Primero pulse Importar datos.'))
        self._configure_category_accounting()
        data=self._source()
        warehouses={'FABRICA CALZADO':self.warehouse_factory_id,'CBBA':self.warehouse_cbba_id,'SCZ':self.warehouse_scz_id}
        groups=defaultdict(list)
        for row in data['stock']:
            groups[(row['branch'],row['product'])].append(row)
        notes=[]
        valuation_warnings=[]
        applied_quantities=defaultdict(float)
        applied=0
        for (branch,key), rows in groups.items():
            mark='balance:'+branch+':'+key
            if self._ref(mark):continue
            product=self._ref(key)
            warehouse=warehouses[branch]
            company=warehouse.company_id
            if not product:
                notes.append('Saldo sin producto: '+key)
                continue
            qty=sum(float(r['qty'] or 0) for r in rows)
            if qty<0:
                notes.append('Saldo negativo no cargado: '+key)
                continue
            if any(self._uom(r['uom'])!=product.uom_id for r in rows):
                notes.append('Unidad de saldo incompatible: '+key)
                continue
            scoped=product.with_company(company)
            costs=[float(r['cost']) for r in rows if isinstance(r['cost'],(int,float)) and r['cost']>0]
            # Never reset an opening balance on top of operational movements.
            if self.env['stock.move'].search_count([('product_id','=',product.id),('company_id','=',company.id),('state','=','done')]):
                notes.append('Saldo omitido: producto con movimientos previos '+product.display_name+' / '+branch)
                continue
            quants=self.env['stock.quant'].with_company(company).with_context(inventory_mode=True)
            current=quants.search([('product_id','=',product.id),('company_id','=',company.id)])
            if any(q.quantity or q.reserved_quantity or q.inventory_quantity_set for q in current):
                notes.append('Saldo omitido: existencias o conteos previos '+product.display_name+' / '+branch)
                continue
            if costs:
                if max(costs)-min(costs)>0.00001:
                    notes.append('Costos contradictorios: '+key)
                    continue
                scoped.standard_price=costs[0]
            if qty and scoped.standard_price<=0:
                if key.startswith('pt:') and scoped.standard_price == 0:
                    valuation_warnings.append('%s / %s: %s pares cargados con costo cero. Falta regularizar valoración.' % (product.display_name, branch, qty))
                else:
                    notes.append('Saldo pendiente: falta costo válido de apertura '+product.display_name+' / '+branch)
                    continue
            if qty:
                quant=quants.create({'product_id':product.id,'location_id':warehouse.lot_stock_id.id,'inventory_quantity':qty})
                result=quant.with_context(inventory_name='Apertura Tosscano — saldo al 23/10/2026').action_apply_inventory()
                if isinstance(result,dict):
                    raise UserError(_('Odoo requiere resolver un conflicto de inventario: %s',product.display_name))
            self._bind(mark,product)
            applied+=1
            if key.startswith('pt:'):
                applied_quantities[branch]+=qty
        if valuation_warnings:
            self.valuation_pending_log = '\n'.join(filter(None, [self.valuation_pending_log, '\n'.join(valuation_warnings)]))
        self.write({'stock_imported':not notes,'import_log':(self.import_log or '')+'\n\nSALDOS: %s posiciones aplicadas en esta ejecución.\n'%applied+'\n'.join(notes)+
                    '\nTerminados cargados en esta ejecución: '+', '.join('%s: %s pares' % (b, q) for b, q in sorted(applied_quantities.items()))+
                    ('\nHay saldos de terminados cargados sin costo. Consulte Saldos cargados sin costo de apertura.' if self.valuation_pending_log else '')+
                    '\nFecha de movimientos: fecha de ejecución nativa. Corte de origen: 23/10/2026. No se reescriben fechas.'})
        return True
