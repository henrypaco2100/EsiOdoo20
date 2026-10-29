import json
import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError


class Bom(models.Model):
    _inherit = 'mrp.bom'

    def esi_get_output_selection_grid(self):
        self.ensure_one()
        self.check_access('read')
        self._check_shared_variants()
        if not self.esi_multi_variant:
            raise UserError(_('Seleccione una receta compartida entre tallas.'))
        grid = self.product_tmpl_id.esi_get_recipe_selection_grid()
        allowed = set(self.esi_allowed_variant_ids.ids)
        rows = [row for row in grid['matrix'] if any(c.get('product_id') in allowed for c in row[1:])]
        columns = [i for i in range(1, len(grid['header'])) if any(row[i].get('product_id') in allowed for row in rows)]
        return {'header': [grid['header'][0]] + [grid['header'][i] for i in columns],
            'matrix': [[row[0]] + [dict(row[i], is_possible_combination=bool(row[i].get('is_possible_combination') and row[i].get('product_id') in allowed)) for i in columns] for row in rows]}


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_output_grid_changes = fields.Text(store=False)
    esi_output_selection_json = fields.Text(compute='_compute_output_selection_json')

    @api.depends('esi_output_line_ids.product_id', 'esi_output_line_ids.quantity')
    def _compute_output_selection_json(self):
        for mo in self:
            mo.esi_output_selection_json = json.dumps([
                {'product_id': line.product_id.id, 'quantity': line.quantity}
                for line in mo.esi_output_line_ids if line.product_id])

    @api.onchange('esi_output_grid_changes')
    def _onchange_output_grid_changes(self):
        if not self.esi_output_grid_changes:
            return
        if self.state != 'draft' or not self.esi_variant_line_mode:
            raise UserError(_('Las tallas se seleccionan en una OF por tallas en borrador.'))
        try:
            payload = json.loads(self.esi_output_grid_changes)
            if payload['bom_id'] != self.esi_plan_bom_id.id:
                raise ValueError()
            allowed = {p.id: p for p in self.esi_plan_bom_id.esi_allowed_variant_ids}
            rows, seen = [], set()
            for cell in payload['quantities']:
                pid, qty = cell['product_id'], float(cell['qty'])
                if pid not in allowed or pid in seen or not math.isfinite(qty) or qty < 0:
                    raise ValueError()
                seen.add(pid)
                if qty:
                    if allowed[pid].uom_id.is_zero(qty):
                        raise ValueError()
                    rows.append(Command.create({'product_id': pid, 'quantity': qty}))
            if not rows:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise UserError(_('Seleccione tallas permitidas y al menos una cantidad positiva.')) from exc
        self.esi_output_line_ids = [Command.clear()] + rows
        self._onchange_output_lines()
        self.esi_output_grid_changes = False
