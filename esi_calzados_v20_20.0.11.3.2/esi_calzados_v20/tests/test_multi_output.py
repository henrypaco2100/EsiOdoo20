from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged, Form


@tagged('post_install', '-at_install')
class TestMultiOutput(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('mrp.group_mrp_byproducts') | cls.env.ref('mrp.group_mrp_manager')
        attribute = cls.env['product.attribute'].create({'name': 'Talla prueba', 'esi_highlight_card': True, 'esi_group_production': True,
            'value_ids': [Command.create({'name': str(n)}) for n in (40, 41, 42)]})
        cls.template = cls.env['product.template'].create({'name': 'Botín prueba', 'is_storable': True,
            'attribute_line_ids': [Command.create({'attribute_id': attribute.id, 'value_ids': [Command.set(attribute.value_ids.ids)]})]})
        cls.products = cls.template.product_variant_ids.sorted('id')
        cls.material = cls.env['product.product'].create({'name': 'Material prueba', 'esi_component_ok': True, 'is_storable': True})
        cls.bom = cls.env['mrp.bom'].create({'product_tmpl_id': cls.template.id, 'product_qty': 1,
            'bom_line_ids': [Command.create({'product_id': cls.material.id, 'product_qty': 2, 'uom_id': cls.material.uom_id.id})]})
        cls.operation = cls.env['stock.picking.type'].search([('code', '=', 'mrp_operation'), ('company_id', '=', cls.env.company.id)], limit=1)

    def _group(self):
        return self.env['esi.production.group'].create({'mode': 'multi', 'responsible_id': self.env.uid,
            'picking_type_id': self.operation.id,
            'line_ids': [Command.create({'product_id': p.id, 'quantity': q, 'bom_id': self.bom.id}) for p, q in zip(self.products, (10, 20, 30))]})

    def test_one_order_three_outputs_and_no_source_changes(self):
        group = self._group()
        group.action_create_productions()
        self.assertEqual(len(group.production_ids), 1)
        mo = group.production_ids
        self.assertEqual({m.product_id.id: m.product_uom_qty for m in mo.move_finished_ids}, dict(zip(self.products.ids, (10, 20, 30))))
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 120)
        self.assertEqual(self.bom.bom_line_ids.product_qty, 2)
        self.assertFalse(group.batch_bom_id.active)
        self.assertEqual(mo._get_backorder_mo_vals()['esi_group_id'], group.id)
        self.assertFalse(self.bom.byproduct_ids)
        self.assertAlmostEqual(sum(mo.move_byproduct_ids.mapped('cost_share')), 50)
        group.action_create_productions()
        self.assertEqual(len(group.production_ids), 1)
        with self.assertRaises(UserError):
            group.line_ids[0].quantity = 99

    def test_native_completion_keeps_distinct_inventory(self):
        group = self._group()
        group.action_create_productions()
        mo = group.production_ids
        self.env['stock.quant']._update_available_quantity(self.material, mo.location_src_id, 120)
        mo.action_assign()
        with Form(mo) as form:
            form.qty_producing = mo.product_qty
        mo.button_mark_done()
        self.assertEqual(mo.state, 'done')
        for p, qty in zip(self.products, (10, 20, 30)):
            quants = self.env['stock.quant'].search([('product_id', '=', p.id), ('location_id', '=', mo.location_dest_id.id)])
            self.assertEqual(sum(quants.mapped('quantity')), qty)

    def test_bad_recipe_refused(self):
        group = self._group()
        self.bom.product_id = self.products[0]
        with self.assertRaises(UserError):
            group.action_create_productions()

    def test_attribute_visible(self):
        for p in self.products:
            self.assertIn('Talla prueba:', p.esi_variant_highlight)
        self.assertIn('40', self.template.esi_variant_highlight)
