from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from .test_direct_plan import TestDirectSizePlan
from ..hooks import mark_existing_components


@tagged('post_install', '-at_install')
class TestComponents(TestDirectSizePlan):
    def test_non_component_rejected_in_recipe(self):
        finished = self.products[:1]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.bom.write({'bom_line_ids': [Command.create({'product_id': finished.id, 'product_qty': 1})]})

    def test_non_component_rejected_in_mo(self):
        mo = self.env['mrp.production'].create({'product_id': self.products[0].id,
            'bom_id': self.bom.id, 'picking_type_id': self.picking.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            mo.write({'move_raw_ids': [Command.create({'name': 'Not allowed', 'product_id': self.products[1].id,
                'product_uom_qty': 1, 'uom_id': self.products[1].uom_id.id,
                'location_id': mo.location_src_id.id, 'location_dest_id': mo.production_location_id.id})]})

    def test_catalog_only_raw_materials_filtered(self):
        domain = self.bom.with_context(child_field='bom_line_ids')._get_product_catalog_domain()
        self.assertNotIn(self.products[0], self.env['product.product'].search(domain))
        self.assertIn(self.material, self.env['product.product'].search(domain))
        domain = self.bom.with_context(child_field='byproduct_ids')._get_product_catalog_domain()
        self.assertIn(self.products[0], self.env['product.product'].search(domain))

    def test_migration_marks_only_existing_materials(self):
        self.material.esi_component_ok = False
        mark_existing_components(self.env)
        self.assertTrue(self.material.esi_component_ok)
        self.assertFalse(any(self.products.mapped('esi_component_ok')))
        mark_existing_components(self.env)
        self.assertTrue(self.material.esi_component_ok)

    def test_recipe_grid_is_scoped_to_template(self):
        grid = self.template.esi_get_recipe_selection_grid(self.products.ids + self.material.ids)
        cells = [cell for row in grid['matrix'] for cell in row[1:] if cell['product_id']]
        self.assertEqual({c['product_id'] for c in cells}, set(self.template.product_variant_ids.ids))
        self.assertEqual({c['product_id'] for c in cells if c['qty']}, set(self.products.ids))
        self.assertEqual(len(grid['header']) - 1, 3)
        self.assertEqual(len(grid['matrix']), 2)
