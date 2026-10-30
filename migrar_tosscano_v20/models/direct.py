import hashlib
import json
from collections import defaultdict
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import file_open
from .size_policy import required_sizes

FINISHED_ALIASES = {'M-W-01-010': 'M-W-01-10', 'M-BT-01-010': 'M-BT-01-10'}


class DirectMigration(models.Model):
    _inherit = 'tosscano.migration'

    data_imported = fields.Boolean(readonly=True, copy=False)
    stock_imported = fields.Boolean(readonly=True, copy=False)
    import_log = fields.Text(string='Resultado de importación', readonly=True, copy=False)
    valuation_pending_log = fields.Text(string='Historial de saldos cargados sin costo', readonly=True, copy=False)
    product_count = fields.Integer(string='Productos/variantes vinculados', readonly=True, copy=False)
    recipe_log = fields.Text(string='Resultado de creación de recetas en Fábrica', readonly=True, copy=False)

    def _source(self):
        with file_open('migrar_tosscano_v20/data/direct.json', 'r') as stream:
            data = json.load(stream)
        for row in data['finished']:
            row['sizes'] = required_sizes(row)
        return data

    def _lock(self):
        self._check_scope()
        if str(self.cutoff) != '2026-10-28':
            raise UserError(_('Este paquete corresponde al corte 28/10/2026 y está preparado para una base nueva. No reutilice el registro del corte anterior.'))
        required = {'esi_material_type', 'esi_measure', 'esi_component_ok', 'esi_manufacture_ok', 'product_add_mode'}
        if required - set(self.env['product.template']._fields):
            raise UserError(_('Actualice primero esi_calzados_v20 a la versión 20.0.11.3.0 o posterior y verifique sale_product_matrix.'))
        if any(c.currency_id.name != 'BOB' for c in (self.root_id | self.factory_id | self.cbba_id | self.scz_id)):
            raise UserError(_('Los costos de origen están en bolivianos. Las compañías seleccionadas deben usar BOB.'))
        self.env.cr.execute('SELECT pg_advisory_xact_lock(20261028, 27102026)')
        self.invalidate_recordset()

    def _xmlname(self, key):
        # Stable across repeated runs/configurations; company scope is explicit.
        scope = '%s:%s:%s' % (self.root_id.id, self.factory_id.id, key)
        return 'import_' + hashlib.sha256(scope.encode()).hexdigest()

    def _ref(self, key):
        record = self._exact_ref(key)
        if record:
            return record
        # Keep old product, recipe and balance identities. Never import an old
        # opening balance a second time just because its code was corrected.
        for old, official in FINISHED_ALIASES.items():
            token = 'pt:' + official
            if key.endswith(token) or token + ':' in key:
                legacy = key.replace(token, 'pt:' + old, 1)
                record = self._exact_ref(legacy)
                if record:
                    return record
        return record

    def _exact_ref(self, key):
        return self.env.ref('tosscano_import_data.' + self._xmlname(key), raise_if_not_found=False)

    def _finished_conflict(self, row):
        for old, official in FINISHED_ALIASES.items():
            if row['code'] != official:
                continue
            previous = self._exact_ref('pt:' + old)
            current = self._exact_ref('pt:' + official)
            if previous and current and previous != current:
                return ('Código %s: ya existen dos plantillas vinculadas (%s y %s). '
                        'No se fusionan ni se recargan saldos; requieren consolidación de sus existencias/documentos.'
                        % (official, previous.id, current.id))
        return False

    def _bind(self, key, record):
        self.env['ir.model.data'].create({'module': 'tosscano_import_data',
            'name': self._xmlname(key), 'model': record._name, 'res_id': record.id, 'noupdate': True})
        return record

    def _category_root(self, name):
        model = self.env['product.category']
        root = model.search([('name', '=ilike', name), ('parent_id', '=', False)])
        if len(root) > 1:
            raise UserError(_('Hay varias categorías raíz llamadas %s.', name))
        return root or model.create({'name': name})

    def _category(self, family, subfamily=None, root_name='Materia prima'):
        root = self._category_root(root_name)
        parent = root
        for level, name in enumerate([family, subfamily]):
            if not name:
                continue
            name = ' '.join(name.upper().split())
            found = self.env['product.category'].search([('name', '=', name), ('parent_id', '=', parent.id if parent else False)])
            if len(found) > 1:
                raise UserError(_('Categorías duplicadas con el mismo padre: %s', name))
            if level == 0 and not found:
                # Move the existing family, keeping its ID, children, product
                # assignments and accounting properties intact.
                legacy = self.env['product.category'].search([('name', '=', name), ('parent_id', '=', False)])
                if len(legacy) > 1:
                    raise UserError(_('Familia duplicada: %s', name))
                if legacy and legacy != root:
                    legacy.write({'parent_id': root.id})
                    found = legacy
            parent = found or self.env['product.category'].create({'name': name, 'parent_id': parent.id if parent else False})
        return parent

    def action_group_categories(self):
        self._lock()
        data = self._source()
        roots = {name: self._category_root(name) for name in ('Materia prima', 'Producto terminado')}
        # Collect actual trees first: a manually shared tree cannot be moved
        # into both roots. Let the user separate that tree explicitly.
        branches = {}
        for kind, rows in [('Materia prima', data['materials']), ('Producto terminado', data['finished'])]:
            for row in rows:
                record = self._ref(row['key'])
                if not record:
                    continue
                category = record.categ_id
                while category.parent_id and category.parent_id not in list(roots.values()):
                    category = category.parent_id
                if category in list(roots.values()):
                    if category != roots[kind]:
                        raise UserError(_('Un producto está asignado directamente a la raíz incorrecta: %s.', record.display_name))
                    continue
                if category.id in branches and branches[category.id][1] != kind:
                    raise UserError(_('La categoría %s contiene terminados y materias primas importados. Separe esa clasificación antes de agrupar.', category.display_name))
                branches[category.id] = (category, kind)
        for category, kind in branches.values():
            if category.parent_id != roots[kind]:
                category.write({'parent_id': roots[kind].id})
        # Also build/reuse the source paths for subsequent imports.
        for row in data['materials']:
            self._category(row.get('family') or 'MATERIAS PRIMAS', row.get('subfamily') or 'OTROS MATERIALES')
        for row in data['finished']:
            self._category('CALZADOS ' + row['family'], row['subfamily'], 'Producto terminado')
        self._configure_category_accounting()
        self.import_log = (self.import_log or '') + '\nCategorías agrupadas bajo Materia prima y Producto terminado. Se conservan familias, subfamilias y productos.'
        return True

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

    @staticmethod
    def _size_sort_key(value):
        """Sort footwear sizes numerically, keeping unusual labels after numbers."""
        text = str(value).strip()
        try:
            return (0, float(text.replace(',', '.')), text)
        except ValueError:
            return (1, 0.0, text.upper())

    @classmethod
    def _ordered_attribute_values(cls, name, values):
        # The source catalogue may arrive in any order.  Talla must always be
        # presented numerically (34, 35, 36...) in variants and matrices.
        unique = list(dict.fromkeys(values))
        if name == 'Talla':
            return sorted(unique, key=cls._size_sort_key)
        return unique

    def _attribute_line(self, name, values, grouped=False):
        attr = self._attribute(name, grouped)
        ids = []
        ordered_values = self._ordered_attribute_values(name, values)
        for position, name_value in enumerate(ordered_values, start=1):
            value_model = self.env['product.attribute.value']
            value = value_model.search([('attribute_id', '=', attr.id), ('name', '=', str(name_value))], limit=2)
            if len(value) > 1:
                raise UserError(_('Valor de atributo duplicado: %s', name_value))
            vals = {'attribute_id': attr.id, 'name': str(name_value)}
            if name == 'Talla' and 'sequence' in value_model._fields:
                # Sequence is global to the Talla value, so derive it from the
                # numeric size itself instead of from the current template.
                try:
                    vals['sequence'] = int(round(float(str(name_value).replace(',', '.')) * 100))
                except ValueError:
                    vals['sequence'] = 100000 + position
            if not value:
                value = value_model.create(vals)
            elif name == 'Talla' and 'sequence' in value._fields and value.sequence != vals.get('sequence'):
                value.sequence = vals['sequence']
            ids.append(value.id)
        return (0, 0, {'attribute_id': attr.id, 'value_ids': [(6, 0, ids)]})

    def _material(self, row):
        product = self._ref(row['key'])
        if product:
            if not product.esi_component_ok:
                product.product_tmpl_id.write({'esi_component_ok': True})
            return product
        company = self.factory_id
        uom = self._uom(row['uom'])
        existing = self.env['product.product'].with_context(active_test=False).search([('default_code', '=', row['code']), ('company_id', '=', company.id)])
        if existing:
            if len(existing) != 1 or existing.uom_id != uom or not existing.is_storable:
                raise UserError(_('Código existente incompatible: %s', row['code']))
            # Enable components without changing stock, prices or categories.
            if not existing.esi_component_ok:
                existing.product_tmpl_id.write({'esi_component_ok': True})
            return self._bind(row['key'], existing)
        template = self.env['product.template'].with_company(company).create({
            'name': row['name'], 'default_code': row['code'], 'type': 'consu', 'is_storable': True,
            'company_id': company.id, 'uom_id': uom.id, 'categ_id': self._category(row.get('family') or 'MATERIAS PRIMAS', row.get('subfamily') or 'OTROS MATERIALES').id,
            'purchase_ok': True, 'sale_ok': False, 'esi_component_ok': True,
            'esi_manufacture_ok': False, 'esi_measure': str(row.get('measure') or ''), 'esi_material_type': str(row.get('type') or ''),
            'standard_price': float(row.get('cost') or 0),
        })
        return self._bind(row['key'], template.product_variant_id)

    def _finished(self, row):
        if self._finished_conflict(row):
            return False
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
                'uom_id': self._uom('PAR').id, 'categ_id': self._category('CALZADOS ' + row['family'], row['subfamily'], 'Producto terminado').id,
                'sale_ok': True, 'purchase_ok': False, 'esi_manufacture_ok': True, 'esi_component_ok': False,
                'product_add_mode': 'matrix',
                'attribute_line_ids': lines,
            })
            self._bind(row['key'], template)
        else:
            # Aliases may contribute sizes absent in the original factory row.
            line = template.attribute_line_ids.filtered(lambda l: l.attribute_id.name == 'Talla')
            if len(line) != 1:
                raise UserError(_('La plantilla %s debe tener un único atributo Talla.', template.display_name))
            required = self._attribute_line('Talla', row['sizes'], True)[2]['value_ids'][0][2]
            missing = set(required) - set(line.value_ids.ids)
            if missing:
                line.write({'value_ids': [(4, value_id) for value_id in sorted(missing)]})
        finish_vals = {}
        if not template.esi_manufacture_ok:
            finish_vals['esi_manufacture_ok'] = True
        if 'product_add_mode' in template._fields and template.product_add_mode != 'matrix':
            finish_vals['product_add_mode'] = 'matrix'
        if finish_vals:
            template.write(finish_vals)
        for product in template.product_variant_ids:
            size = product.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id.name == 'Talla').name
            key = row['key'] + ':' + size
            expected = row['code'] + '-T' + size
            if product.default_code != expected:
                occupied = self.env['product.product'].with_context(active_test=False).search_count([
                    ('default_code', '=', expected), ('id', '!=', product.id)])
                if occupied:
                    raise UserError(_('Código %s ocupado por otro producto; no se duplicó.', expected))
                product.default_code = expected
            if not self._ref(key):
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
            conflict = self._finished_conflict(row)
            if conflict:
                notes.append(conflict)
            else:
                self._finished(row)
        self._accounts(data['accounts'], notes)
        self._configure_category_accounting()
        notes.extend(self._apply_finished_costs(data))
        notes.extend(self._import_sale_prices(data))
        notes.append('Recetas: use el botón 3. Crear recetas (Fábrica) después de importar los datos.')
        self.write({'data_imported': True, 'loaded': True,
                    'product_count': len(data['materials']) + sum(len(r['sizes']) for r in data['finished']),
                    'import_log': '\n'.join(['DATOS IMPORTADOS', 'Categorías: familia → subfamilia.',
                    'Unidades: '+', '.join(data['units']),
                    '%s materias primas; %s plantillas de calzado.' % (len(data['materials']), len(data['finished'])),
                    'Terminados obtenidos de las hojas de existencias; no del archivo de recetas duplicado.',
                    'Modelos separados por código/color; variantes Talla y Color. Las descripciones originales se conservan.',
                    'Costos unitarios de terminados incluidos en BOB, por talla y compañía.'] + notes)})
        return True

    @staticmethod
    def _recipe_norm_text(value):
        return ' '.join(str(value or '').upper().split())

    def _recipe_find_component_exact(self, data, row):
        """Resolve one approved-LDM component without guessing or converting.

        Production rule: the approved Excel is authoritative.  We only accept a
        unique existing material with the exact code, the same normalized name,
        and the exact inventory UoM.  Missing products are NOT created here and
        no alternate code, size expansion or cost-equivalent conversion is used.
        """
        code = (row.get('code') or '').strip()
        if not code:
            return False, _('fila %s sin código de componente') % row.get('row')

        candidates = []
        for material in data.get('materials', []):
            if (material.get('code') or '').strip() != code:
                continue
            product = self._ref(material['key'])
            if product:
                candidates.append(product)
        if not candidates:
            candidates = list(self.env['product.product'].with_context(active_test=False).search([
                ('default_code', '=', code),
                ('company_id', '=', self.factory_id.id),
                ('esi_component_ok', '=', True),
            ], limit=3))
        unique = list({product.id: product for product in candidates}.values())
        if not unique:
            return False, _('código %s no existe en la materia prima migrada') % code
        if len(unique) > 1:
            return False, _('código %s está duplicado en materia prima') % code

        product = unique[0]
        excel_name = self._recipe_norm_text(row.get('name'))
        product_name = self._recipe_norm_text(product.name)
        if excel_name != product_name:
            return False, _("código %s: nombre Excel '%s' ≠ producto '%s'") % (
                code, row.get('name') or '', product.name or '')

        source_uom = self._uom(row.get('uom') or '')
        if product.uom_id != source_uom:
            return False, _("código %s: UDM Excel '%s' ≠ UDM producto '%s'") % (
                code, source_uom.name, product.uom_id.name)
        return product, False

    def _ensure_recipe_quantity_precision(self):
        """Preserve the approved per-pair quantities down to four decimals.

        ``mrp.bom.line.product_qty`` uses the global ``Product Unit`` decimal
        precision in Odoo 20.  The approved military sheets contain values such
        as 0.0455, 0.0698 and 0.0496, so a 2/3-decimal database would silently
        alter the recipe.  We only raise the precision when needed and never
        reduce an existing higher precision.
        """
        precision = self.env['decimal.precision'].search([('name', '=', 'Product Unit')], limit=1)
        if not precision:
            raise UserError(_("No existe la precisión decimal 'Product Unit'; no se crearán LdM porque no se puede garantizar 4 decimales."))
        if precision.digits < 4:
            precision.digits = 4
        return precision.digits

    def _recipe_center_route(self, recipe):
        """Return the five approved factory work centers for one military BoM.

        The approved cost sheets consistently identify the production stages as
        Cortado, Aparado, Conformado, Solado and Terminado.  In ESI's factory
        those stages are the work centers CORTE, APARADO, CONFORMADO, SOLADO and
        TERMINADO.  We only link existing work centers; they are never created,
        renamed or guessed by this migration.

        ``minutes_per_unit`` is deliberately omitted so esi_calzados_v20 keeps
        its own default.  The Excel values beside the stages are COSTS, not
        minutes, therefore they must never be copied into production duration.
        """
        expected = [
            ('Cortado', 'CORTE'),
            ('Aparado', 'APARADO'),
            ('Conformado', 'CONFORMADO'),
            ('Solado', 'SOLADO'),
            ('Terminado', 'TERMINADO'),
        ]
        source_stages = {self._recipe_norm_text(name) for name, _cost in recipe.get('overhead', [])}
        errors = []
        route = []
        for sequence, (excel_name, center_name) in enumerate(expected, start=1):
            if self._recipe_norm_text(excel_name) not in source_stages:
                errors.append(_("la ficha %s no contiene la etapa '%s'") % (recipe.get('code'), excel_name))
                continue

            # Prefer the center owned by FABRICA.  A global center is accepted
            # only when there is no company-specific one.  Duplicates are an
            # explicit configuration error; the migrator never picks one at random.
            centers = self.env['mrp.workcenter'].with_context(active_test=False).search([
                ('name', '=ilike', center_name),
                ('company_id', '=', self.factory_id.id),
            ])
            if not centers:
                centers = self.env['mrp.workcenter'].with_context(active_test=False).search([
                    ('name', '=ilike', center_name),
                    ('company_id', '=', False),
                ])
            if not centers:
                errors.append(_("no existe el centro de trabajo '%s' para FABRICA") % center_name)
                continue
            if len(centers) > 1:
                errors.append(_("hay %s centros de trabajo llamados '%s'; deje uno solo para FABRICA") % (
                    len(centers), center_name))
                continue
            if not centers.active:
                errors.append(_("el centro de trabajo '%s' está archivado") % center_name)
                continue
            route.append((0, 0, {
                'sequence': sequence * 10,
                'workcenter_id': centers.id,
            }))
        return route, errors

    def _recipes(self, data, notes):
        """Create LdM exactly as approved in FICHAS DE COSTO MILITAR.

        - exact component code
        - exact approved quantity per pair
        - exact approved UoM
        - no size-dependent substitutions
        - no creation of missing materials
        - no cost-equivalent UoM conversions
        - no partial BoMs: any mismatch leaves that BoM pending
        """
        created = existing = pending = 0
        for recipe in data['recipes']:
            targets = [row for row in data['finished'] if row['code'].startswith(recipe['code'] + '-')]
            if not targets:
                notes.append('LdM %s pendiente: no hay producto terminado de ese modelo en los inventarios recibidos.' % recipe['code'])
                pending += 1
                continue
            components = [row for row in data['components']
                          if row['recipe'] == recipe['code'] and float(row.get('qty_per_pair') or 0) > 0]
            if not components:
                notes.append('LdM %s no creada: la ficha aprobada no tiene componentes con cantidad positiva.' % recipe['code'])
                pending += 1
                continue

            center_route, center_errors = self._recipe_center_route(recipe)
            if center_errors:
                notes.append('LdM %s NO CREADA. Corrija primero el recorrido por centros:\n- %s' % (
                    recipe['code'], '\n- '.join(center_errors)))
                pending += len(targets)
                continue

            for row in targets:
                if self._finished_conflict(row):
                    continue
                key = 'bom:' + row['key']
                if self._ref(key):
                    existing += 1
                    continue
                template = self._ref(row['key'])
                if not template:
                    notes.append('Producto sin importar para LdM %s: %s' % (recipe['code'], row['code']))
                    pending += 1
                    continue
                matches = self.env['mrp.bom'].with_context(active_test=False).search([
                    ('company_id', '=', self.factory_id.id),
                    ('product_tmpl_id', '=', template.id),
                    ('code', '=', recipe['code']),
                ], limit=1)
                if matches:
                    notes.append('Ya existe una LdM para %s / %s; no se modificó.' % (recipe['code'], row['code']))
                    existing += 1
                    continue

                lines = []
                errors = []
                for component in components:
                    product, error = self._recipe_find_component_exact(data, component)
                    if error:
                        errors.append('fila %s [%s] %s: %s' % (
                            component.get('row'), component.get('code') or '', component.get('name') or '', error))
                        continue
                    # Product UoM was validated to be exactly the approved Excel UoM.
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'product_qty': float(component['qty_per_pair']),
                        'uom_id': product.uom_id.id,
                    }))

                if errors:
                    notes.append('LdM %s / %s NO CREADA. Corrija primero estas diferencias:\n- %s' % (
                        recipe['code'], row['code'], '\n- '.join(errors)))
                    pending += 1
                    continue

                allowed = template.product_variant_ids
                if not allowed:
                    notes.append('LdM %s / %s no creada: plantilla sin variantes almacenables.' % (recipe['code'], row['code']))
                    pending += 1
                    continue
                bom = self.env['mrp.bom'].with_company(self.factory_id).create({
                    'product_tmpl_id': template.id,
                    'company_id': self.factory_id.id,
                    'product_qty': 1,
                    'uom_id': template.uom_id.id,
                    'type': 'normal',
                    'code': recipe['code'],
                    'esi_multi_variant': True,
                    'esi_allowed_variant_ids': [(6, 0, allowed.ids)],
                    'esi_center_route_ids': center_route,
                    'bom_line_ids': lines,
                })
                self._bind(key, bom)
                created += 1

        notes.insert(0, 'Fábrica: %s. %s LdM exactas creadas, %s ya existentes, %s pendientes.' % (
            self.factory_id.display_name, created, existing, pending))
        notes.insert(1, 'Fuente autoritativa: FICHAS DE COSTO MILITAR APROBADO(3).xlsx. Cantidades por par conservadas exactamente (p. ej. 0,0455 sigue siendo 0,0455); sin sustituciones por talla ni conversiones automáticas de UDM.')
        notes.insert(2, 'Cada LdM creada queda con recorrido CORTE → APARADO → CONFORMADO → SOLADO → TERMINADO; si falta o se duplica un centro, la LdM no se crea.')

    def action_complete_sizes(self):
        self._lock()
        if not self.data_imported:
            raise UserError(_('Primero pulse 1. Importar datos.'))
        if not self.env.user.has_group('account.group_account_manager') or not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Se requieren permisos de administrador de Contabilidad e Inventario.'))
        data = self._source()
        notes = []
        for row in data['finished']:
            conflict = self._finished_conflict(row)
            if conflict:
                notes.append(conflict)
            elif self._ref(row['key']):
                self._finished(row)
            else:
                notes.append('Producto no importado: ' + row['code'])
        # Give newly created variants their confirmed opening cost in each branch.
        # Existing cost revision markers preserve subsequent native AVCO changes.
        notes.extend(self._apply_finished_costs(data))
        self.import_log = (self.import_log or '') + '\n\nTALLAS COMPLETADAS\n' + '\n'.join([
            'Rango 34–46 para líneas no infantiles. Escolar/infantil conserva sus tallas. No se cargaron saldos.'
        ] + notes)
        return True

    def action_create_recipes(self):
        self._lock()
        if not self.data_imported:
            raise UserError(_('Primero pulse 1. Importar datos.'))
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requieren permisos de administrador de Fabricación.'))
        notes = []
        digits = self._ensure_recipe_quantity_precision()
        notes.append('Precisión Product Unit verificada: %s decimales (mínimo requerido: 4).' % digits)
        self._recipes(self._source(),notes)
        self.recipe_log = '\n'.join(notes)
        self.import_log = (self.import_log or '')+'\n\nRECETAS EN FÁBRICA\n'+self.recipe_log
        return True

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
            finished_row = next((r for r in data.get('finished', []) if key.startswith(r['key'] + ':')), None)
            if finished_row and self._finished_conflict(finished_row):
                message = self._finished_conflict(finished_row)
                if message not in notes:
                    notes.append(message)
                continue
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
                result=quant.with_context(inventory_name='Apertura Tosscano — saldo al 28/10/2026').action_apply_inventory()
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
                    '\nFecha de movimientos: fecha de ejecución nativa. Corte de origen: 28/10/2026. No se reescriben fechas.'})
        return True

    def _apply_finished_costs(self, data):
        """Native cost write, once per product/company/source-price revision.

        Existing quantities and dated documents are never changed. Odoo creates
        its native product.value adjustment at the execution date when needed.
        """
        if not self.env.user.has_group('account.group_account_manager') or not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Se requieren permisos de administrador de Contabilidad e Inventario.'))
        notes = []
        applied = 0
        seen = set()
        companies = self.root_id | self.factory_id | self.cbba_id | self.scz_id
        for row in data['finished']:
            templates = self.env['product.template']
            template = self._ref(row['key'])
            if template:
                templates |= template
            # Also value old duplicates if both were imported before the alias
            # was confirmed; do not merge or delete their operational records.
            for old, official in FINISHED_ALIASES.items():
                if row['code'] == official:
                    old_template = self._exact_ref('pt:' + old)
                    if old_template:
                        templates |= old_template
            if not templates:
                notes.append('Costo pendiente, producto no importado: ' + row['code'])
                continue
            cost = float(row['cost'])
            if cost <= 0:
                raise UserError(_('Costo de terminado no válido: %s', row['code']))
            for product in templates.with_context(active_test=False).product_variant_ids:
                for company in companies:
                    identity = (product.id, company.id)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    mark = 'finished-cost:20261028:%s:%s:%.8f' % (company.id, product.id, cost)
                    if self._ref(mark):
                        continue
                    scoped = product.with_company(company)
                    if abs(scoped.standard_price - cost) > 0.0000001:
                        scoped.write({'standard_price': cost})
                        applied += 1
                    self._bind(mark, product)
        notes.append('Costos de terminados: %s actualizaciones por variante/compañía; sin recargar cantidades. '
                     'Las repeticiones no sobrescriben el promedio posterior. Ajuste de valoración nativo a fecha de ejecución.' % applied)
        return notes

    def action_update_finished_costs(self):
        self._lock()
        data = self._source()
        notes = []
        for row in data['finished']:
            conflict = self._finished_conflict(row)
            if conflict:
                notes.append(conflict)
            elif self._ref(row['key']):
                self._finished(row)
        notes.extend(self._apply_finished_costs(data))
        self.import_log = (self.import_log or '') + '\n\nCÓDIGOS Y COSTOS DE TERMINADOS\n' + '\n'.join(notes)
        return True

    def action_fix_product_flags(self):
        self._lock()
        data = self._source()
        material_templates = self.env['product.template']
        finished_templates = self.env['product.template']
        for row in data['materials']:
            product = self._ref(row['key'])
            if product:
                material_templates |= product.product_tmpl_id
        # Support products imported by the original row-based version too.
        material_templates |= self.line_ids.filtered(
            lambda line: line.kind == 'material' and line.product_id).product_id.product_tmpl_id
        for row in data['finished']:
            template = self._ref(row['key'])
            if template:
                finished_templates |= template
        if not material_templates and not finished_templates:
            raise UserError(_('Todavía no hay productos vinculados. Primero pulse Importar datos.'))
        changed_materials = material_templates.filtered(lambda p: not p.esi_component_ok)
        changed_finished = finished_templates.filtered(lambda p: not p.esi_manufacture_ok)
        changed_matrix = finished_templates.filtered(
            lambda p: 'product_add_mode' in p._fields and p.product_add_mode != 'matrix')
        changed_materials.write({'esi_component_ok': True})
        changed_finished.write({'esi_manufacture_ok': True})
        if changed_matrix:
            changed_matrix.write({'product_add_mode': 'matrix'})
        message = _('%s materias primas marcadas como Componentes; %s terminados marcados como Fabricar; '
                    '%s terminados configurados con selección Matrix.',
                    len(changed_materials), len(changed_finished), len(changed_matrix))
        self.import_log = (self.import_log or '') + '\n' + message
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Productos actualizados'), 'message': message,
                           'type': 'success', 'sticky': True}}
