import json
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from .test_output_lines import TestOutputLines


@tagged('post_install', '-at_install')
class TestOutputGrid(TestOutputLines):
    def test_grid_contains_only_recipe_variants(self):
        self._line_values()
        allowed = self.products[:2]
        self.bom.esi_allowed_variant_ids = [Command.set(allowed.ids)]
        grid = self.bom.esi_get_output_selection_grid()
        self.assertEqual(len(grid['header']) - 1, 2)
        cells = [c for row in grid['matrix'] for c in row[1:] if c['is_possible_combination']]
        self.assertEqual({c['product_id'] for c in cells}, set(allowed.ids))

    def test_grid_replaces_unsaved_lines_without_creating_orders(self):
        values = self._line_values()
        values['product_id'] = self.products[0].id
        count = self.env['mrp.production'].search_count([])
        mo = self.env['mrp.production'].new(values)
        mo.esi_output_grid_changes = json.dumps({'bom_id': self.bom.id, 'quantities':[
            {'product_id': self.products[0].id, 'qty':30},
            {'product_id': self.products[1].id, 'qty':0},
            {'product_id': self.products[2].id, 'qty':10}]})
        mo._onchange_output_grid_changes()
        self.assertEqual(len(mo.esi_output_line_ids), 2)
        self.assertEqual(sum(mo.esi_output_line_ids.mapped('quantity')), 40)
        self.assertFalse(mo.esi_output_grid_changes)
        self.assertEqual(self.env['mrp.production'].search_count([]), count)

    def test_grid_rejects_wrong_recipe(self):
        values = self._line_values()
        values['product_id'] = self.products[0].id
        mo = self.env['mrp.production'].new(values)
        mo.esi_output_grid_changes = json.dumps({'bom_id': -1, 'quantities':[]})
        with self.assertRaises(UserError):
            mo._onchange_output_grid_changes()
