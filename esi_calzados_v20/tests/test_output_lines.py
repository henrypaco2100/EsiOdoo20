from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from .test_direct_plan import TestDirectSizePlan


@tagged('post_install', '-at_install')
class TestOutputLines(TestDirectSizePlan):
    def _line_values(self, quantities=(20,20,10)):
        self.bom.write({'esi_multi_variant': True, 'esi_allowed_variant_ids': [Command.set(self.products.ids)]})
        return {'company_id': self.env.company.id, 'picking_type_id': self.picking.id,
            'esi_template_id': self.template.id, 'esi_plan_bom_id': self.bom.id,
            'esi_variant_line_mode': True, 'esi_output_line_ids': [Command.create({
                'product_id': p.id, 'quantity': q}) for p, q in zip(self.products, quantities)]}

    def test_lines_drive_native_moves(self):
        mo = self.env['mrp.production'].create(self._line_values())
        self.assertEqual(mo.esi_output_total, 50)
        self.assertEqual(mo.esi_total_output_qty, 50)
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 100)
        self.assertEqual(sorted(mo.move_finished_ids.mapped('product_uom_qty')), [10,20,20])
        self.assertFalse(mo.bom_id.esi_multi_variant)
        self.assertFalse(mo.bom_id.active)
        self.assertEqual(self.bom.bom_line_ids.product_qty, 2)
        mo.write({'esi_output_line_ids': [Command.update(mo.esi_output_line_ids[0].id, {'quantity': 30})]})
        self.assertEqual(mo.esi_total_output_qty, 60)
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 120)
        mo.action_confirm()
        with self.assertRaises(UserError), self.cr.savepoint():
            mo.esi_output_line_ids[0].write({'quantity': 1})

    def test_direct_child_edit_rebuilt_before_confirmation(self):
        mo = self.env['mrp.production'].create(self._line_values())
        mo.esi_output_line_ids[0].write({'quantity': 30})
        self.assertTrue(mo.esi_outputs_dirty)
        mo.action_confirm()
        self.assertEqual(mo.esi_total_output_qty, 60)
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 120)

    def test_shared_recipe_rejects_other_color(self):
        self._line_values()
        red = (self.template.product_variant_ids - self.products)[:1]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.bom.write({'esi_allowed_variant_ids': [Command.link(red.id)]})

    def test_lookup_respects_allowed_variants(self):
        self._line_values()
        red = self.template.product_variant_ids - self.products
        found = self.env['mrp.bom']._bom_find(self.template.product_variant_ids, company_id=self.env.company.id, bom_type='normal')
        self.assertTrue(all(found.get(p) == self.bom for p in self.products))
        self.assertFalse(any(found.get(p) == self.bom for p in red))

    def test_excluded_output_rejected(self):
        vals = self._line_values()
        red = (self.template.product_variant_ids - self.products)[:1]
        vals['esi_output_line_ids'].append(Command.create({'product_id': red.id, 'quantity': 10}))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['mrp.production'].create(vals)

    def test_foreign_line_rejected(self):
        mo = self.env['mrp.production'].create(self._line_values())
        other = self.env['mrp.production'].create(self._line_values())
        with self.assertRaises(UserError), self.cr.savepoint():
            mo.write({'esi_output_line_ids': [Command.update(other.esi_output_line_ids[0].id, {'quantity': 2})]})

    def test_copy_retains_distribution(self):
        mo = self.env['mrp.production'].create(self._line_values())
        copied = mo.copy()
        self.assertEqual(copied.esi_output_total, 50)
        self.assertEqual(copied.esi_total_output_qty, 50)
        self.assertFalse(copied.esi_output_line_ids & mo.esi_output_line_ids)
