import json
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestDirectSizePlan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('mrp.group_mrp_manager') | cls.env.ref('mrp.group_mrp_byproducts') | cls.env.ref('product.group_product_manager')
        cls.size = cls.env['product.attribute'].create({'name': 'Talla directa', 'esi_group_production': True,
            'value_ids': [Command.create({'name': str(v)}) for v in [39,40,41]]})
        cls.color = cls.env['product.attribute'].create({'name': 'Color directo',
            'value_ids': [Command.create({'name': v}) for v in ['Negro','Rojo']]})
        cls.template = cls.env['product.template'].create({'name': 'Calzado directo', 'is_storable': True,
            'attribute_line_ids': [Command.create({'attribute_id': attr.id,
                'value_ids': [Command.set(attr.value_ids.ids)]}) for attr in [cls.size, cls.color]]})
        cls.products = cls.template.product_variant_ids.filtered(lambda p: 'Negro' in p.product_template_attribute_value_ids.mapped('name')).sorted('id')
        cls.material = cls.env['product.product'].create({'name': 'Material común', 'esi_component_ok': True, 'is_storable': True})
        cls.bom = cls.env['mrp.bom'].create({'product_tmpl_id': cls.template.id, 'product_qty': 1,
            'bom_line_ids': [Command.create({'product_id': cls.material.id, 'product_qty': 2})]})
        cls.picking = cls.env['stock.picking.type'].search([('company_id','=',cls.env.company.id),('code','=','mrp_operation')],limit=1)

    def _grid(self, quantities):
        return json.dumps({'header': [{'name':''}] + [{'name': str(i)} for i in range(len(quantities))],
            'matrix': [[{'name':''}] + [{'qty': q, 'ptav_ids': sorted(p.product_template_attribute_value_ids.ids),
                'is_possible_combination': True} for p,q in zip(self.products,quantities)]]})

    def _values(self, quantities):
        return {'company_id': self.env.company.id, 'picking_type_id': self.picking.id,
            'esi_template_id': self.template.id, 'product_id': self.products[0].id,
            'esi_plan_bom_id': self.bom.id, 'esi_plan_grid': self._grid(quantities)}

    def test_direct_create_without_persisted_group(self):
        groups = self.env['esi.production.group'].search_count([])
        mo = self.env['mrp.production'].create(self._values([20,20,10]))
        self.assertFalse(mo.esi_group_id)
        self.assertEqual(self.env['esi.production.group'].search_count([]), groups)
        self.assertEqual(mo.product_id, self.products[0])
        self.assertEqual(mo.product_qty, 20)
        self.assertEqual(mo.esi_total_output_qty, 50)
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 100)
        self.assertEqual(sorted(mo.move_finished_ids.mapped('product_uom_qty')), [10,20,20])
        mo.write({'esi_plan_grid': self._grid([10,10,10])})
        self.assertEqual(mo.esi_total_output_qty, 30)
        self.assertEqual(sum(mo.move_raw_ids.mapped('product_uom_qty')), 60)
        self.assertEqual(self.bom.bom_line_ids.product_qty, 2)
        mo.action_confirm()
        with self.assertRaises(UserError):
            mo.write({'esi_plan_grid': self._grid([20,20,20])})

    def test_onchange_does_not_create_recipes(self):
        count = self.env['mrp.bom'].with_context(active_test=False).search_count([])
        mo = self.env['mrp.production'].new({'company_id': self.env.company.id,
            'esi_template_id': self.template.id, 'picking_type_id': self.picking.id})
        mo._onchange_esi_template()
        self.assertTrue(mo.product_id)
        self.assertFalse(mo.esi_plan_grid)
        self.assertEqual(self.env['mrp.bom'].with_context(active_test=False).search_count([]), count)

    def test_other_color_rejected(self):
        vals = self._values([20,20,10])
        grid = json.loads(vals['esi_plan_grid'])
        red = (self.template.product_variant_ids - self.products)[0]
        grid['matrix'][0][2]['ptav_ids'] = sorted(red.product_template_attribute_value_ids.ids)
        vals['esi_plan_grid'] = json.dumps(grid)
        with self.assertRaises(UserError):
            self.env['mrp.production'].create(vals)

    def test_zero_reference_rejected(self):
        with self.assertRaises(UserError):
            self.env['mrp.production'].create(self._values([0,20,10]))
