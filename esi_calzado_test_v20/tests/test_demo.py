from odoo.tests import TransactionCase, tagged
from ..models.demo import STAGES


@tagged('post_install', '-at_install')
class TestFootwearDemo(TransactionCase):
    def test_demo_recipes_and_repeat_button(self):
        self.env.user.group_ids += self.env.ref('mrp.group_mrp_manager') | self.env.ref('product.group_product_manager') | self.env.ref('mrp.group_mrp_byproducts') | self.env.ref('mrp.group_mrp_routings')
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
        original_quantities = demo.bom_ids.bom_line_ids.mapped('product_qty')
        demo.group_id.action_create_productions()
        orders = demo.group_id.production_ids
        self.assertEqual(len(orders), 2)
        self.assertEqual(sorted(orders.mapped('esi_total_output_qty')), [30, 50])
        batch = orders.filtered('esi_size_batch')
        self.assertEqual(len(batch), 1)
        self.assertEqual(len(batch.workorder_ids), 5)
        self.assertEqual(sorted(batch.move_finished_ids.mapped('product_uom_qty')), [10, 20, 20])
        leather = batch.move_raw_ids.filtered(lambda m: 'Cuero para capellada' in m.product_id.name)
        self.assertAlmostEqual(leather.product_uom_qty, 400)
        soles = batch.move_raw_ids.filtered(lambda m: 'Suela -' in m.product_id.name)
        self.assertEqual(sorted(soles.mapped('product_uom_qty')), [10, 20, 20])
        self.assertEqual(demo.bom_ids.bom_line_ids.mapped('product_qty'), original_quantities)
        # Native inventory receives each finished SKU independently.
        for mo in orders:
            for move in mo.move_raw_ids:
                qty = move.uom_id._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
                self.env['stock.quant']._update_available_quantity(move.product_id, move.location_id, qty)
            mo.action_assign()
            mo.qty_producing = mo.product_qty
            mo._set_qty_producing()
            mo._mark_byproducts_as_produced()
            for wo in mo.workorder_ids:
                wo.button_start()
                wo.button_finish()
            mo.button_mark_done()
            self.assertEqual(mo.state, 'done')
            for move in mo.move_finished_ids:
                self.assertAlmostEqual(move.quantity, move.product_uom_qty)
