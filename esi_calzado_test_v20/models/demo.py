from odoo import fields, models, Command, _
from odoo.exceptions import UserError

STAGES = ('Corte', 'Aparado', 'Conformado', 'Solado', 'Terminado')
RECIPES = (
    ('Botín Industrial Andino', 8.0, 0.35, 0.30, 25.0, 0.060, (10, 20, 8, 15, 6)),
    ('Zapato Ejecutivo Urbano', 6.0, 0.28, 0.25, 22.0, 0.050, (8, 18, 6, 12, 5)),
    ('Zapatilla Casual Sierra', 5.0, 0.25, 0.22, 18.0, 0.040, (7, 15, 5, 10, 4)),
)


class CalzadoDemo(models.Model):
    _name = 'esi.calzado.demo'
    _description = 'Demo de calzado por compañía'
    _inherit = 'esi.branch.mixin'
    _check_company_auto = True

    name = fields.Char(default='Demo de Calzado', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([('draft', 'Sin generar'), ('ready', 'Demo preparada')], default='draft', readonly=True)
    template_ids = fields.Many2many('product.template', string='Calzados terminados', readonly=True)
    material_ids = fields.Many2many('product.product', string='Materias primas', readonly=True)
    bom_ids = fields.Many2many('mrp.bom', string='Recetas', readonly=True)
    workcenter_ids = fields.Many2many('mrp.workcenter', string='Centros de trabajo', readonly=True)
    group_id = fields.Many2one('esi.production.group', string='Grupo inicial', readonly=True, check_company=True)
    _company_unique = models.Constraint('unique(company_id)', 'Ya existe una demo para esta compañía. Abra la existente.')

    def write(self, vals):
        if 'company_id' in vals and any(d.state == 'ready' for d in self):
            raise UserError(_('La demo preparada no puede cambiar de compañía.'))
        return super().write(vals)

    def action_prepare(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requiere Responsable de Fabricación para preparar la demo.'))
        if self.company_id not in self.env.companies:
            raise UserError(_('Active primero la sucursal seleccionada.'))
        if not self.env['product.template'].has_access('create') or not self.env['uom.uom'].has_access('create'):
            raise UserError(_('Para preparar la demo también necesita permiso de creación de productos y unidades de medida. Use un administrador de productos.'))
        self.env.cr.execute('SELECT id FROM esi_calzado_demo WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset(['state'])
        if self.state == 'ready':
            return self.action_products()
        demo = self.with_company(self.company_id)
        env = demo.env
        unit = env.ref('uom.product_uom_unit')
        meter = env.ref('uom.product_uom_meter')
        litre = env.ref('uom.product_uom_litre')
        pair = env['uom.uom'].create({'name': '[DEMO] PAR', 'relative_factor': 1})
        foot2 = env['uom.uom'].create({'name': '[DEMO] PIE²', 'relative_uom_id': env.ref('uom.product_uom_square_meter').id, 'relative_factor': 0.09290304})
        attrs = {}
        for seq, (label, names) in enumerate((('Talla', ['40', '41', '42']), ('Color', ['Negro', 'Café']),
                ('Modelo', ['Clásico', 'Reforzado']), ('Material', ['Cuero', 'Microfibra'])), 1):
            attrs[label] = env['product.attribute'].create({'name': '[DEMO] ' + label, 'sequence': seq,
                'create_variant': 'always', 'esi_highlight_card': label in ('Talla', 'Color'),
                'value_ids': [Command.create({'name': n}) for n in names]})
        centers = env['mrp.workcenter']
        for i, stage in enumerate(STAGES, 1):
            centers |= env['mrp.workcenter'].create({'name': '[DEMO] ' + stage,
                'code': 'DEMO-%s-%s' % (self.id, i), 'company_id': self.company_id.id,
                'costs_hour': (20, 25, 20, 25, 18)[i-1]})
        materials = env['product.product']
        def material(name, uom, price=0.0):
            nonlocal materials
            product = env['product.product'].create({'name': '[DEMO] ' + name, 'type': 'consu', 'is_storable': True,
                'company_id': self.company_id.id, 'uom_id': uom.id, 'sale_ok': False, 'purchase_ok': True,
                'standard_price': price})
            materials |= product
            return product
        leather = material('Cuero para capellada', foot2, 3)
        micro = material('Microfibra ancho 1,40 m', meter, 35)
        lining = material('Forro textil ancho 1,40 m', meter, 20)
        thread = material('Hilo de aparado', meter, 0.05)
        glue_ap = material('Adhesivo para aparado', litre, 30)
        counter = material('Contrafuerte', unit, 1)
        toe = material('Puntera reforzada', unit, 4)
        glue = material('Adhesivo de solado', litre, 40)
        primer = material('Preparador para suela', litre, 30)
        insole = material('Plantilla de confort', pair, 3)
        box = material('Caja para un par', unit, 2)
        creams = {color: material('Acabado ' + color, litre, 25) for color in ('Negro', 'Café')}
        templates = env['product.template']
        boms = env['mrp.bom']
        demo_lines = []
        operation_type = env['stock.picking.type'].search([('code', '=', 'mrp_operation'), ('company_id', '=', self.company_id.id)], limit=1)
        if not operation_type:
            raise UserError(_('Configure un almacén con operación de fabricación en esta sucursal.'))
        for index, (name, leather_qty, micro_qty, lining_qty, thread_qty, glue_qty, minutes) in enumerate(RECIPES, 1):
            template = env['product.template'].create({'name': '[DEMO] ' + name, 'type': 'consu', 'is_storable': True,
                'company_id': self.company_id.id, 'uom_id': pair.id, 'product_add_mode': 'matrix',
                'sale_ok': True, 'purchase_ok': False, 'list_price': (250, 180, 150)[index-1],
                'attribute_line_ids': [Command.create({'attribute_id': a.id, 'value_ids': [Command.set(a.value_ids.ids)]}) for a in attrs.values()]})
            templates |= template
            for number, product in enumerate(template.product_variant_ids.sorted('id'), 1):
                product.default_code = 'DEMO-%s-Z%s-%03d' % (self.id, index, number)
            sole_template = env['product.template'].create({'name': '[DEMO] Suela - ' + name,
                'type': 'consu', 'is_storable': True, 'company_id': self.company_id.id,
                'uom_id': pair.id, 'sale_ok': False, 'purchase_ok': True, 'product_add_mode': 'matrix',
                'attribute_line_ids': [Command.create({'attribute_id': attrs['Talla'].id, 'value_ids': [Command.set(attrs['Talla'].value_ids.ids)]})]})
            materials |= sole_template.product_variant_ids
            sole_template.product_variant_ids.write({'standard_price': (20, 15, 12)[index-1]})
            bom = env['mrp.bom'].create({'product_tmpl_id': template.id, 'company_id': self.company_id.id,
                'product_qty': 1, 'uom_id': pair.id, 'type': 'normal', 'code': 'DEMO-RECETA-%s-%s' % (self.id,index),
                'picking_type_id': operation_type.id, 'allow_operation_dependencies': True})
            boms |= bom
            operations = []
            for i, stage in enumerate(STAGES):
                operation = env['mrp.routing.workcenter'].create({'bom_id': bom.id, 'name': stage,
                    'workcenter_id': centers[i].id, 'sequence': (i+1)*10, 'time_mode': 'manual',
                    'time_cycle_manual': minutes[i],
                    'blocked_by_operation_ids': [Command.set(operations[-1].ids)] if operations else []})
                operations.append(operation)
            ptavs = template.attribute_line_ids.product_template_value_ids
            def condition(attribute, value):
                return ptavs.filtered(lambda v: v.attribute_id == attrs[attribute] and v.name == value)
            def component(product, qty, stage, cond=None):
                env['mrp.bom.line'].create({'bom_id': bom.id, 'product_id': product.id,
                    'product_qty': qty, 'uom_id': product.uom_id.id, 'operation_id': operations[stage].id,
                    'bom_product_template_attribute_value_ids': [Command.set(cond.ids)] if cond else []})
            component(leather, leather_qty, 0, condition('Material', 'Cuero'))
            component(micro, micro_qty, 0, condition('Material', 'Microfibra'))
            component(lining, lining_qty, 0)
            component(thread, thread_qty, 1)
            component(glue_ap, 0.02, 1)
            component(counter, 2, 2)
            component(toe, 2, 2, condition('Modelo', 'Reforzado'))
            for sole in sole_template.product_variant_ids:
                size = sole.product_template_attribute_value_ids.name
                component(sole, 1, 3, condition('Talla', size))
            component(glue, glue_qty, 3)
            component(primer, 0.01, 3)
            component(insole, 1, 4)
            component(box, 1, 4)
            for color, cream in creams.items():
                component(cream, 0.004, 4, condition('Color', color))
            example = template.product_variant_ids.filtered(lambda p: {'40','Negro','Clásico','Cuero'}.issubset(set(p.product_template_attribute_value_ids.mapped('name'))))[:1]
            demo_lines.append(Command.create({'product_id': example.id, 'quantity': 5, 'bom_id': bom.id}))
        group = env['esi.production.group'].create({'company_id': self.company_id.id, 'mode': 'variants',
            'responsible_id': env.uid, 'picking_type_id': operation_type.id, 'line_ids': demo_lines,
            'note': 'DEMO: cinco pares por modelo. Recetas con operaciones y componentes por variante; usar OF por variante.'})
        self.write({'state': 'ready', 'template_ids': [Command.set(templates.ids)],
            'bom_ids': [Command.set(boms.ids)], 'material_ids': [Command.set(materials.ids)],
            'workcenter_ids': [Command.set(centers.ids)], 'group_id': group.id})
        return self.action_products()

    def action_products(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': 'Calzados de demostración', 'res_model': 'product.product',
            'view_mode': 'kanban,list,form', 'domain': [('product_tmpl_id', 'in', self.template_ids.ids)]}
