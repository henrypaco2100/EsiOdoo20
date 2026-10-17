import json
import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_size_batch = fields.Boolean(string='OF agrupada por tallas', readonly=True, copy=True)
    esi_source_bom_id = fields.Many2one('mrp.bom', string='Receta original', readonly=True, copy=True, check_company=True)
    esi_source_base_qty = fields.Float(default=1.0, readonly=True, copy=True)
    esi_batch_attribute_ids = fields.Many2many('product.attribute', string='Atributos agrupados', readonly=True, copy=True)
    esi_size_grid = fields.Text(compute='_compute_size_grid', string='Distribución por talla')
    esi_total_output_qty = fields.Float(compute='_compute_size_grid', string='Total a fabricar')
    esi_batch_description = fields.Char(compute='_compute_size_grid', string='Producto y características')

    @api.depends('move_finished_ids.product_uom_qty', 'move_finished_ids.quantity',
                 'move_finished_ids.state', 'move_finished_ids.product_id', 'move_finished_ids.uom_id',
                 'product_qty', 'product_id', 'uom_id', 'esi_batch_attribute_ids')
    def _compute_size_grid(self):
        for mo in self:
            moves = mo.move_finished_ids.filtered(lambda m: m.state != 'cancel' and m.product_id.product_tmpl_id == mo.product_id.product_tmpl_id)
            grouped = mo.esi_batch_attribute_ids
            fixed = mo.product_id.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id not in grouped)
            mo.esi_batch_description = ' · '.join([mo.product_id.product_tmpl_id.name or ''] + fixed.mapped('name'))
            columns = sorted(moves, key=lambda m: tuple(m.product_id.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id in grouped).mapped('name')))
            headers = [{'name': ''}]
            planned = [{'name': _('Planificado')}]
            actual = [{'name': _('Producido / registrado')}]
            total = 0.0
            for move in columns:
                values = move.product_id.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id in grouped)
                headers.append({'name': ' / '.join(values.mapped('name')) or move.product_id.display_name})
                qty = move.uom_id._compute_quantity(move.product_uom_qty, mo.uom_id, round=False)
                total += qty
                planned.append({'qty': qty, 'is_possible_combination': True})
                actual.append({'qty': move.uom_id._compute_quantity(move.quantity, mo.uom_id, round=False), 'is_possible_combination': True})
            mo.esi_total_output_qty = total if moves else mo.product_qty
            mo.esi_size_grid = json.dumps({'header': headers, 'matrix': [planned, actual]})

    def _get_backorder_mo_vals(self):
        vals = super()._get_backorder_mo_vals()
        # Scalar metadata is copied; totals are always recomputed from this OF's moves.
        vals.update(esi_size_batch=self.esi_size_batch, esi_source_bom_id=self.esi_source_bom_id.id)
        return vals

    def write(self, vals):
        # Native quantity-change wizards rescale the primary output and all byproducts.
        # Do not allow an independent product/recipe substitution on a configured batch.
        if {'product_id', 'bom_id', 'uom_id'}.intersection(vals):
            for mo in self.filtered('esi_size_batch'):
                for key in ('product_id', 'bom_id', 'uom_id'):
                    if key in vals and vals[key] != mo[key].id and not (mo.state == 'draft' and 'esi_plan_grid' in vals):
                        raise UserError(_('No cambie el producto, unidad o receta de una OF agrupada. Cancele la OF y prepare un nuevo grupo con la distribución correcta.'))
        return super().write(vals)


class Workorder(models.Model):
    _inherit = 'mrp.workorder'

    @api.depends('operation_id', 'workcenter_id', 'qty_production',
                 'production_id.move_finished_ids.product_uom_qty',
                 'production_id.move_finished_ids.state', 'production_id.esi_source_base_qty')
    def _compute_duration_expected(self):
        return super()._compute_duration_expected()

    def _get_duration_expected(self, alternative_workcenter=False, ratio=1):
        self.ensure_one()
        mo = self.production_id
        if not mo.esi_size_batch or not self.operation_id or not mo.esi_source_bom_id:
            return super()._get_duration_expected(alternative_workcenter=alternative_workcenter, ratio=ratio)
        center = alternative_workcenter or self.workcenter_id
        if not center or not mo.product_qty:
            return super()._get_duration_expected(alternative_workcenter=alternative_workcenter, ratio=ratio)
        base_qty = mo.uom_id._compute_quantity(mo.esi_source_base_qty, self.uom_id, round=False)
        capacity, setup, cleanup = center._get_capacity(self.product_id, self.uom_id, base_qty)
        # Work order quantities remain native primary-output units. Convert the
        # planned workload to ALL sizes only for scheduling, not stock valuation.
        total_qty = mo.uom_id._compute_quantity(mo.esi_total_output_qty, self.uom_id, round=False)
        primary_qty = mo.uom_id._compute_quantity(mo.product_qty, self.uom_id, round=False)
        workload = total_qty * self.qty_to_produce / primary_qty
        cycles = math.ceil(workload / capacity) if capacity else 0
        return setup + cleanup + cycles * self.operation_id.time_cycle * ratio * 100.0 / center.time_efficiency
