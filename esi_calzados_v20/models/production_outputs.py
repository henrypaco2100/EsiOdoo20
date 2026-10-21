import json
import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from .output_commands import resolve_outputs


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_variant_line_mode = fields.Boolean(string='Fabricar varias tallas', copy=False)
    esi_output_line_ids = fields.One2many('esi.production.output.line', 'production_id',
        string='Variantes a fabricar', copy=False)
    esi_allowed_output_ids = fields.Many2many(related='esi_plan_bom_id.esi_allowed_variant_ids')
    esi_output_total = fields.Float(compute='_compute_output_total', string='Total a fabricar')
    esi_outputs_dirty = fields.Boolean(compute='_compute_output_total')

    @api.depends('esi_output_line_ids.product_id', 'esi_output_line_ids.quantity', 'esi_plan_grid')
    def _compute_output_total(self):
        for mo in self:
            mo.esi_output_total = sum(mo.esi_output_line_ids.mapped('quantity'))
            try:
                previous = {tuple(c['ptav_ids']): c['qty'] for row in json.loads(mo.esi_plan_grid or '{}').get('matrix', []) for c in row[1:] if c.get('qty')}
                current = {tuple(sorted(l.product_id.product_template_attribute_value_ids.ids)): l.quantity for l in mo.esi_output_line_ids}
                mo.esi_outputs_dirty = previous != current
            except (ValueError, KeyError, TypeError):
                mo.esi_outputs_dirty = True

    def _esi_load_plan_grid(self):
        # Retain the legacy payload for existing orders; new forms use real lines.
        if self.esi_variant_line_mode or not self._origin.id:
            return
        return super()._esi_load_plan_grid()

    @api.onchange('esi_template_id')
    def _onchange_output_template(self):
        if self.state != 'draft' or self.esi_group_id:
            return
        if self.esi_plan_bom_id.product_tmpl_id != self.esi_template_id:
            self.esi_plan_bom_id = False
            self.esi_output_line_ids = [Command.clear()]
        if not self.esi_plan_bom_id and self.esi_template_id:
            self.esi_plan_bom_id = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', self.esi_template_id.id), ('esi_multi_variant', '=', True),
                ('company_id', 'in', [False, self.company_id.id]), ('type', '=', 'normal')],
                order='sequence,id', limit=1)
        self._onchange_output_recipe()

    @api.onchange('esi_plan_bom_id', 'esi_variant_line_mode')
    def _onchange_output_recipe(self):
        if self.state != 'draft' or self.esi_group_id:
            return
        # Direct footwear orders always use size lines, including while the
        # user is still selecting the shared recipe. Keep the technical flag
        # for native backorders and group-generated orders handled separately.
        self.esi_variant_line_mode = True
        if not self.esi_plan_bom_id:
            return
        allowed = self.esi_plan_bom_id.esi_allowed_variant_ids
        self.esi_output_line_ids = self.esi_output_line_ids.filtered(lambda line: line.product_id in allowed)
        if self.product_id not in allowed:
            # The current native recipe may belong to another color/material.
            # Release it before selecting a permitted reference variant.
            self.bom_id = False
            self.product_id = allowed[:1]
        self.esi_plan_dirty = True

    @api.onchange('esi_output_line_ids')
    def _onchange_output_lines(self):
        if self.state == 'draft' and self.esi_variant_line_mode:
            valid = self.esi_output_line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
            if valid:
                primary = valid.sorted(lambda l: (-l.quantity, l.product_id.id))[:1]
                self.product_id = primary.product_id
                self.product_qty = primary.quantity
                self.uom_id = primary.product_id.uom_id
            self.esi_plan_dirty = True

    def _esi_values_from_output_lines(self, vals, existing=None):
        old = {line.id: {'product_id': line.product_id.id, 'quantity': line.quantity}
            for line in existing.esi_output_line_ids} if existing else {}
        try:
            rows = resolve_outputs(old, vals.get('esi_output_line_ids', []))
        except (ValueError, TypeError) as exc:
            raise UserError(str(exc)) from exc
        bom_id = vals.get('esi_plan_bom_id', existing.esi_plan_bom_id.id if existing else False)
        bom = self.env['mrp.bom'].browse(bom_id).exists()
        bom.check_access('read')
        if not bom or not bom.esi_multi_variant:
            raise UserError(_('Seleccione una receta compartida con variantes permitidas.'))
        bom._check_shared_variants()
        products = self.env['product.product'].browse([pid for pid, qty in rows]).exists()
        products.check_access('read')
        if len(products) != len(rows):
            raise UserError(_('Alguna variante ya no existe.'))
        bom._esi_check_allowed_products(products)
        rows.sort(key=lambda item: (-item[1], item[0]))
        lookup = {p.id: p for p in products}
        grid = {'matrix': [[{'name': ''}] + [{'ptav_ids': sorted(lookup[pid].product_template_attribute_value_ids.ids), 'qty': qty}
            for pid, qty in rows]]}
        values = dict(vals, esi_plan_grid=json.dumps(grid), product_id=rows[0][0],
            esi_template_id=bom.product_tmpl_id.id, esi_variant_line_mode=True)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            if values.get('esi_variant_line_mode'):
                values = self._esi_values_from_output_lines(values)
            elif values.get('esi_output_line_ids'):
                raise UserError(_('Seleccione una receta compartida para utilizar la lista de variantes.'))
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        watched = {'esi_output_line_ids', 'esi_variant_line_mode', 'esi_plan_bom_id',
            'esi_plan_grid', 'esi_template_id', 'product_id', 'product_qty', 'bom_id', 'uom_id', 'company_id', 'picking_type_id'}
        if watched.intersection(vals):
            result = True
            for mo in self:
                enabled = vals.get('esi_variant_line_mode', mo.esi_variant_line_mode)
                if mo.esi_variant_line_mode and not enabled:
                    raise UserError(_('No desactive una distribución guardada. Cancele esta OF y cree otra si desea cambiar el modo.'))
                if enabled and mo.state == 'draft':
                    mo.check_access('write')
                    values = mo._esi_values_from_output_lines(vals, mo)
                elif enabled and {'esi_output_line_ids', 'esi_plan_bom_id', 'esi_plan_grid', 'esi_template_id', 'esi_variant_line_mode'}.intersection(vals):
                    raise UserError(_('La lista de tallas solo se modifica en borrador.'))
                elif not enabled and vals.get('esi_output_line_ids'):
                    raise UserError(_('Seleccione una receta compartida para fabricar varias tallas.'))
                else:
                    values = vals
                result = super(Production, mo).write(values) and result
            return result
        return super().write(vals)

    def action_confirm(self):
        for mo in self.filtered(lambda m: m.esi_variant_line_mode and m.state == 'draft'):
            # Rebuild even after a direct child-model edit, before native reservation.
            mo.write({'esi_output_line_ids': []})
        return super().action_confirm()

    def _get_backorder_mo_vals(self):
        values = super()._get_backorder_mo_vals()
        # Remaining quantities are owned by native moves, not the initial plan.
        values.update(esi_variant_line_mode=False, esi_output_line_ids=[], esi_plan_grid=False)
        return values

    def copy_data(self, default=None):
        result = super().copy_data(default=default)
        for mo, vals in zip(self, result):
            if mo.esi_variant_line_mode and 'esi_variant_line_mode' not in (default or {}):
                vals.update(esi_variant_line_mode=True, esi_output_line_ids=[Command.create({
                    'product_id': line.product_id.id, 'quantity': line.quantity}) for line in mo.esi_output_line_ids])
        return result


class OutputLine(models.Model):
    _name = 'esi.production.output.line'
    _description = 'Variante terminada de una orden de fabricación'
    _order = 'id'
    _check_company_auto = True

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    product_id = fields.Many2one('product.product', string='Variante / talla', required=True, check_company=True)
    quantity = fields.Float(string='Cantidad a fabricar', required=True, default=1, digits='Product Unit')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    planned_qty = fields.Float(compute='_compute_native_quantities', string='Plan vigente')
    produced_qty = fields.Float(compute='_compute_native_quantities', string='Registrado')

    @api.depends('product_id', 'production_id.move_finished_ids.product_id',
        'production_id.move_finished_ids.product_uom_qty', 'production_id.move_finished_ids.quantity',
        'production_id.move_finished_ids.state', 'production_id.move_finished_ids.uom_id')
    def _compute_native_quantities(self):
        for line in self:
            moves = line.production_id.move_finished_ids.filtered(lambda m: m.product_id == line.product_id and m.state != 'cancel')
            line.planned_qty = sum(m.uom_id._compute_quantity(m.product_uom_qty, line.uom_id, round=False) for m in moves)
            line.produced_qty = sum(m.uom_id._compute_quantity(m.quantity, line.uom_id, round=False) for m in moves)

    @api.constrains('product_id', 'quantity', 'production_id')
    def _check_output(self):
        for line in self:
            mo = line.production_id
            if not math.isfinite(line.quantity) or line.quantity <= 0 or line.uom_id.is_zero(line.quantity):
                raise ValidationError(_('La cantidad por talla debe ser mayor que cero.'))
            if not mo.esi_variant_line_mode or not mo.esi_plan_bom_id.esi_multi_variant:
                raise ValidationError(_('La orden requiere una receta compartida.'))
            mo.esi_plan_bom_id._esi_check_allowed_products(line.product_id)
            if len(mo.esi_output_line_ids.filtered(lambda l: l.product_id == line.product_id)) > 1:
                raise ValidationError(_('No repita una variante en la misma orden.'))

    def _check_parent_edit(self, parents):
        parents.check_access('write')
        if any(m.state != 'draft' for m in parents):
            raise UserError(_('Solo se pueden editar tallas de una orden en borrador.'))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env['mrp.production'].browse([v.get('production_id') for v in vals_list if v.get('production_id')])
        self._check_parent_edit(parents)
        return super().create(vals_list)

    def write(self, vals):
        if 'production_id' in vals:
            raise UserError(_('No se pueden trasladar líneas a otra orden.'))
        self._check_parent_edit(self.production_id)
        return super().write(vals)

    def unlink(self):
        self._check_parent_edit(self.production_id)
        return super().unlink()
