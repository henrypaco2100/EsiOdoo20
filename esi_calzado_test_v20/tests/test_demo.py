from odoo.tests import TransactionCase, tagged
from ..models.demo import STAGES


@tagged('post_install', '-at_install')
class TestFootwearDemo(TransactionCase):
    def test_demo_recipes_and_repeat_button(self):
        self.env.user.group_ids += self.env.ref('mrp.group_mrp_manager') | self.env.ref('product.group_product_manager')
        demo = self.env['esi.calzado.demo'].search([('company_id', '=', self.env.company.id)], limit=1)
        if not demo:
            demo = self.env['esi.calzado.demo'].create({})
        demo.action_prepare()
        self.assertEqual(len(demo.template_ids), 3)
        self.assertEqual(len(demo.template_ids.product_variant_ids), 72)
        self.assertEqual(len(demo.bom_ids), 3)
        self.assertEqual(len(demo.workcenter_ids), 5)
        for bom in demo.bom_ids:
            operations = bom.operation_ids.sorted('sequence')
            self.assertEqual(operations.mapped('name'), list(STAGES))
            for previous, current in zip(operations, operations[1:]):
                self.assertEqual(current.blocked_by_operation_ids, previous)
            self.assertTrue(all(bom.bom_line_ids.mapped('operation_id')))
            for variant in bom.product_tmpl_id.product_variant_ids:
                used = bom.bom_line_ids.filtered(lambda line: not line._skip_bom_line(variant))
                self.assertEqual(len(used.filtered(lambda line: 'Suela -' in line.product_id.name)), 1)
                self.assertEqual(len(used.filtered(lambda line: 'Acabado ' in line.product_id.name)), 1)
        templates = demo.template_ids
        demo.action_prepare()
        self.assertEqual(demo.template_ids, templates)
        self.assertFalse(demo.group_id.production_ids)
