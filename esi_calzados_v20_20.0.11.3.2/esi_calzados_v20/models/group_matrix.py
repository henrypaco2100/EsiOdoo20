import json
import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class Template(models.Model):
    _inherit = 'product.template'

    def esi_get_production_matrix(self):
        self.ensure_one()
        self.check_access('read')
        lines = self.valid_product_template_attribute_line_ids
        if math.prod(len(l.product_template_value_ids) for l in lines) > 250:
            raise UserError(_('La cuadrícula admite hasta 250 combinaciones.'))
        if any(l.attribute_id.create_variant != 'always' for l in lines):
            raise UserError(_('Utilice creación instantánea de variantes para esta cuadrícula.'))
        products = self.product_variant_ids
        grouped = lines.attribute_id.filtered('esi_group_production')
        # With no grouping flag, keep a useful axis but do not change OF grouping.
        axis = grouped or lines[:1].attribute_id
        columns, rows, cells = {}, {}, {}
        for product in products:
            values = product.product_template_attribute_value_ids
            col = values.filtered(lambda v: v.attribute_id in axis).sorted(lambda v: (v.attribute_id.sequence, v.id))
            row = values - col
            ckey, rkey = tuple(col.ids), tuple(sorted(row.ids))
            columns[ckey] = ' / '.join(col.mapped('name')) or _('Cantidad')
            rows[rkey] = ' · '.join(row.mapped('name')) or ' '
            cells[(rkey, ckey)] = {'qty': 0, 'ptav_ids': sorted(values.ids),
                'is_possible_combination': self._is_combination_possible(values)}
        if not any(cell['is_possible_combination'] for cell in cells.values()):
            raise UserError(_('El producto no tiene variantes activas válidas para seleccionar.'))
        return {'header': [{'name': ''}] + [{'name': label} for label in columns.values()],
                'matrix': [[{'name': label}] + [cells.get((rkey, ckey),
                    {'qty': 0, 'is_possible_combination': False}) for ckey in columns]
                    for rkey, label in rows.items()]}


class Group(models.Model):
    _inherit = 'esi.production.group'
    esi_grid_changes = fields.Text(store=False)
    esi_grid_template_id = fields.Many2one('product.template', store=False)
    esi_grid_data = fields.Text(store=False)

    @api.onchange('company_id')
    def _clear_grid_company(self):
        self.esi_grid_template_id = False
        self.esi_grid_data = False
        self.esi_grid_changes = False

    @api.onchange('esi_grid_template_id')
    def _load_size_grid(self):
        self.esi_grid_data = False
        template = self.esi_grid_template_id
        if not template:
            return
        if self.state != 'draft' or self.production_ids:
            raise UserError(_('Las variantes solo se pueden elegir antes de generar las OF.'))
        if not template.is_storable or (template.company_id and template.company_id != self.company_id):
            raise UserError(_('Seleccione un producto almacenable de esta compañía o compartido.'))
        grid = template.esi_get_production_matrix()
        quantities = {}
        for line in self.line_ids.filtered(lambda l: l.product_id.product_tmpl_id == template):
            key = tuple(sorted(line.product_id.product_template_attribute_value_ids.ids))
            if key in quantities:
                raise UserError(_('Unifique las líneas duplicadas de la misma variante antes de abrir la cuadrícula.'))
            quantities[key] = line.quantity
        for row in grid['matrix']:
            for cell in row[1:]:
                cell['qty'] = quantities.get(tuple(cell.get('ptav_ids', [])), 0)
        self.esi_grid_data = json.dumps(grid)

    @api.onchange('esi_grid_changes')
    def _apply_size_grid(self):
        if not self.esi_grid_changes:
            return
        if self.state != 'draft' or self.production_ids:
            raise UserError(_('No se pueden cambiar tallas después de generar las OF.'))
        try:
            grid = json.loads(self.esi_grid_changes)
            template = self.env['product.template'].browse(int(grid['template_id'])).exists()
            template.check_access('read')
            if not template or not template.is_storable or (template.company_id and template.company_id != self.company_id):
                raise ValueError()
            products = {tuple(sorted(p.product_template_attribute_value_ids.ids)): p for p in template.product_variant_ids}
            changes = grid['changes']
            if not isinstance(changes, list) or len(changes) > 250:
                raise ValueError()
            seen = set()
            for cell in changes:
                qty = float(cell['qty'])
                key = tuple(sorted(cell['ptav_ids']))
                product = products.get(key)
                if key in seen or not product or not math.isfinite(qty) or qty < 0:
                    raise ValueError()
                if not template._is_combination_possible(product.product_template_attribute_value_ids):
                    raise ValueError()
                if qty and product.uom_id.is_zero(qty):
                    raise ValueError()
                seen.add(key)
                existing = self.line_ids.filtered(lambda l: l.product_id == product)
                if len(existing) > 1:
                    raise ValidationError(_('Hay líneas duplicadas de esta variante. Unifíquelas antes de usar la cuadrícula.'))
                if not qty:
                    self.line_ids -= existing
                elif existing:
                    existing.quantity = qty
                else:
                    self.update({'line_ids': [Command.create({'product_id': product.id, 'quantity': qty})]})
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise UserError(_('Cuadrícula inválida. Revise las variantes, compañía y cantidades.')) from exc
        self.esi_grid_changes = False


class Line(models.Model):
    _inherit = 'esi.production.group.line'
    variant_label = fields.Char(compute='_compute_variant_label', related=False, string='Variantes')

    @api.depends('product_id.product_template_attribute_value_ids')
    def _compute_variant_label(self):
        for line in self:
            line.variant_label = ' · '.join(line.product_id.product_template_attribute_value_ids.mapped('name'))

    product_template_id = fields.Many2one('product.template', compute='_compute_product_template',
        readonly=False, store=True, precompute=True, string='Producto', domain="[('is_storable', '=', True), ('esi_manufacture_ok', '=', True)]")

    @api.depends('product_id')
    def _compute_product_template(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id
