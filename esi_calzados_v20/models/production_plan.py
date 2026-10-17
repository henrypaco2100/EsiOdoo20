import json
import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError
from .grouping_math import production_key


class ProductionPlan(models.Model):
    _inherit = 'mrp.production'

    esi_template_id = fields.Many2one('product.template', string='Plantilla del calzado',
        compute='_compute_esi_template', store=True, readonly=False, precompute=True,
        domain="[('is_storable', '=', True)]")
    esi_plan_bom_id = fields.Many2one('mrp.bom', string='Receta común', check_company=True,
        domain="[('product_tmpl_id', '=', esi_template_id), ('product_id', '=', False), ('type', '=', 'normal'), ('company_id', 'in', [False, company_id])]")
    esi_plan_grid = fields.Text(string='Cantidades por talla', copy=False)
    esi_plan_total = fields.Float(compute='_compute_plan_total', string='Total a fabricar')
    esi_plan_dirty = fields.Boolean(store=False, default=False)

    @api.depends('product_id')
    def _compute_esi_template(self):
        for mo in self:
            mo.esi_template_id = mo.product_id.product_tmpl_id

    @api.depends('esi_plan_grid')
    def _compute_plan_total(self):
        for mo in self:
            try:
                matrix = json.loads(mo.esi_plan_grid or '{}').get('matrix', [])
                quantities = [float(c.get('qty', 0)) for row in matrix for c in row[1:]]
                mo.esi_plan_total = sum(q for q in quantities if math.isfinite(q) and q >= 0)
            except (ValueError, TypeError, AttributeError):
                mo.esi_plan_total = 0

    @api.onchange('esi_template_id')
    def _onchange_esi_template(self):
        if self.state != 'draft':
            return
        template = self.esi_template_id
        if self.product_id.product_tmpl_id != template:
            self.product_id = template.product_variant_ids[:1]
            self.esi_plan_grid = False
            self.esi_plan_bom_id = False
        self._esi_load_plan_grid()

    @api.onchange('product_id')
    def _onchange_esi_reference(self):
        if self.state == 'draft':
            if self.esi_template_id != self.product_id.product_tmpl_id:
                self.esi_template_id = self.product_id.product_tmpl_id
            self._esi_load_plan_grid()

    def _esi_load_plan_grid(self):
        self.ensure_one()
        # Group-created orders retain their prepared snapshot and output matrix.
        if self.esi_group_id:
            return
        product = self.product_id
        template = product.product_tmpl_id
        grouped = template.attribute_line_ids.attribute_id.filtered('esi_group_production')
        if not product or not grouped:
            self.esi_plan_grid = False
            self.esi_plan_bom_id = False
            return
        grid = template.esi_get_production_matrix()
        reference = sorted(product.product_template_attribute_value_ids.ids)
        row = next((r for r in grid['matrix'] if any(c.get('ptav_ids') == reference for c in r[1:])), None)
        if not row:
            raise UserError(_('La variante de referencia no tiene una combinación válida.'))
        try:
            previous = {tuple(c.get('ptav_ids', [])): float(c.get('qty', 0))
                for r in json.loads(self.esi_plan_grid or '{}').get('matrix', []) for c in r[1:]}
        except (ValueError, TypeError, AttributeError):
            previous = {}
        has_previous = any(previous.get(tuple(c.get('ptav_ids', [])), 0) for c in row[1:])
        row[0] = {'name': ''}
        for cell in row[1:]:
            cell['qty'] = previous.get(tuple(cell.get('ptav_ids', [])), 0) if has_previous else (
                (self.product_qty or 1.0) if cell.get('ptav_ids') == reference else 0)
        grid['matrix'] = [row]
        self.esi_plan_grid = json.dumps(grid)
        if self.esi_plan_bom_id.product_tmpl_id != template:
            self.esi_plan_bom_id = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', template.id), ('product_id', '=', False), ('type', '=', 'normal'),
                ('company_id', 'in', [False, self.company_id.id])], order='sequence,id', limit=1)

    @api.onchange('esi_plan_grid')
    def _onchange_esi_plan_quantities(self):
        if not self.esi_plan_grid or not self.product_id or self.state != 'draft':
            return
        self.esi_plan_dirty = True
        try:
            reference = sorted(self.product_id.product_template_attribute_value_ids.ids)
            for row in json.loads(self.esi_plan_grid)['matrix']:
                for cell in row[1:]:
                    qty = float(cell.get('qty', 0))
                    if cell.get('ptav_ids') == reference and math.isfinite(qty) and qty > 0:
                        self.product_qty = qty
                        self.uom_id = self.product_id.uom_id
        except (KeyError, ValueError, TypeError, AttributeError):
            pass  # Full validation occurs on save; no recipe is created by onchange.

    @api.onchange('esi_plan_bom_id')
    def _onchange_esi_plan_bom(self):
        if self.esi_plan_grid and self.state == 'draft':
            self.esi_plan_dirty = True

    def _esi_prepare_plan_values(self, vals, existing=None):
        if existing and (existing.move_raw_ids.filtered(lambda m: not m.bom_line_id)
                or existing.workorder_ids.filtered(lambda wo: not wo.operation_id)):
            raise UserError(_('Esta OF contiene componentes u operaciones manuales. Prepare una OF nueva para planificarla por tallas desde la receta común.'))
        def value(name, default=False):
            return vals[name] if name in vals else (existing[name].id if existing and self._fields[name].type == 'many2one'
                else existing[name] if existing else default)
        company = self.env['res.company'].browse(value('company_id', self.env.company.id)).exists()
        if not company or company not in self.env.companies:
            raise UserError(_('Active la compañía de la OF.'))
        product = self.env['product.product'].browse(value('product_id')).exists()
        product.check_access('read')
        template = product.product_tmpl_id
        if not product or not product.is_storable or (product.company_id and product.company_id != company):
            raise UserError(_('Seleccione una variante almacenable de esta compañía.'))
        if value('esi_template_id', template.id) != template.id:
            raise UserError(_('La variante no pertenece a la plantilla seleccionada.'))
        grouped = template.attribute_line_ids.attribute_id.filtered('esi_group_production')
        if not grouped:
            raise UserError(_('Marque Agrupar valores en una misma OF en el atributo Talla.'))
        # Also validate the matrix generation limits and instant-variant policy.
        template.esi_get_production_matrix()
        def key(p):
            return production_key(template.id, [(v.attribute_id.id, v.id) for v in p.product_template_attribute_value_ids], grouped.ids, p.id)
        allowed_key = key(product)
        variants = {tuple(sorted(p.product_template_attribute_value_ids.ids)): p for p in template.product_variant_ids}
        selected, seen = {}, set()
        try:
            matrix = json.loads(value('esi_plan_grid'))['matrix']
            cells = [cell for row in matrix for cell in row[1:]]
            if not cells or len(cells) > 250:
                raise ValueError()
            for cell in cells:
                qty = float(cell.get('qty', 0))
                if not math.isfinite(qty) or qty < 0:
                    raise ValueError()
                if not qty:
                    continue
                p = variants.get(tuple(sorted(cell['ptav_ids'])))
                if not p or p.id in seen or key(p) != allowed_key or p.uom_id.is_zero(qty):
                    raise ValueError()
                if not template._is_combination_possible(p.product_template_attribute_value_ids):
                    raise ValueError()
                p.check_access('read')
                seen.add(p.id)
                selected[p] = qty
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise UserError(_('Revise la cuadrícula: cantidades positivas y únicamente tallas de la misma combinación de color, modelo y material.')) from exc
        if product not in selected:
            raise UserError(_('La variante de referencia debe tener cantidad mayor que cero. Elija como referencia una talla que vaya a fabricar.'))
        bom = self.env['mrp.bom'].browse(value('esi_plan_bom_id')).exists()
        bom.check_access('read')
        if not bom or bom.type != 'normal' or bom.product_id or bom.product_tmpl_id != template or (bom.company_id and bom.company_id != company):
            raise UserError(_('Seleccione una receta común de plantilla válida para esta compañía.'))
        picking = self.env['stock.picking.type'].browse(value('picking_type_id')).exists()
        if not picking or picking.code != 'mrp_operation' or picking.company_id != company:
            raise UserError(_('Seleccione la operación de fabricación de la compañía.'))
        source = bom
        if len(selected) > 1:
            # Reuse the same recipe builder as groups, but no group is persisted.
            plan = self.env['esi.production.group'].with_company(company).new({
                'name': existing.name if existing else _('OF por tallas'), 'company_id': company.id,
                'picking_type_id': picking.id, 'line_ids': [Command.create({
                    'product_id': p.id, 'quantity': qty, 'bom_id': bom.id}) for p, qty in selected.items()]})
            _, _, bom, source = plan._batch_recipe(plan.line_ids, primary_product=product)
        result = dict(vals)
        # These preview commands reflect the single reference variant and must
        # not override the new native snapshot's computed moves/work orders.
        for name in ('move_raw_ids', 'move_finished_ids', 'move_byproduct_ids', 'workorder_ids'):
            result.pop(name, None)
        result.update(product_id=product.id, esi_template_id=template.id,
            product_qty=selected[product], uom_id=product.uom_id.id, bom_id=bom.id,
            company_id=company.id, esi_size_batch=len(selected) > 1,
            esi_source_bom_id=source.id,
            esi_source_base_qty=source.uom_id._compute_quantity(source.product_qty, product.uom_id, round=False),
            esi_batch_attribute_ids=[Command.set(grouped.ids)], esi_plan_dirty=False)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [self._esi_prepare_plan_values(vals) if vals.get('esi_plan_grid') else vals for vals in vals_list]
        return super().create(prepared)

    def write(self, vals):
        plan_fields = {'esi_plan_grid', 'esi_plan_bom_id', 'esi_template_id', 'product_id', 'company_id', 'picking_type_id'}
        if plan_fields.intersection(vals):
            result = True
            for mo in self:
                grid = vals.get('esi_plan_grid', mo.esi_plan_grid)
                if grid and (mo.esi_plan_grid or vals.get('esi_plan_grid')):
                    mo.check_access('write')
                    if mo.state != 'draft':
                        raise UserError(_('La distribución de tallas solo se modifica en borrador.'))
                    prepared = mo._esi_prepare_plan_values(dict(vals, esi_plan_grid=grid), existing=mo)
                    result = super(ProductionPlan, mo).write(prepared) and result
                elif mo.esi_plan_grid and not grid:
                    raise UserError(_('No borre la distribución de una OF preparada. Cancele y cree una nueva OF si desea usar fabricación individual.'))
                else:
                    result = super(ProductionPlan, mo).write(vals) and result
            return result
        return super().write(vals)
