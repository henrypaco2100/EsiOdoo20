from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestBomTemporaryRows(TransactionCase):
    def test_create_write_and_real_delete(self):
        product = self.env['product.product'].create({'name': 'Virtual test output'})
        component = self.env['product.product'].create({'name': 'Virtual test material', 'esi_component_ok': True})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'bom_line_ids': [(0, 'virtual_1', {'product_id': component.id, 'product_qty': 2}),
                             (2, 'virtual_1162', 0)],
        })
        self.assertEqual(len(bom.bom_line_ids), 1)
        self.assertEqual(bom.bom_line_ids.product_qty, 2)
        bom.write({'bom_line_ids': [(2, 'virtual_99', 0)]})
        self.assertEqual(len(bom.bom_line_ids), 1)
        bom.write({'bom_line_ids': [(2, bom.bom_line_ids.id, 0)]})
        self.assertFalse(bom.bom_line_ids)

    def test_missing_virtual_update_is_not_discarded(self):
        product = self.env['product.product'].create({'name': 'Missing virtual row'})
        with self.assertRaises(UserError):
            self.env['mrp.bom'].create({'product_tmpl_id': product.product_tmpl_id.id,
                'bom_line_ids': [(1, 'virtual_17', {'product_qty': 2})]})
