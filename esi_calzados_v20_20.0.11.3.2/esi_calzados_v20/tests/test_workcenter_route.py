from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkcenterRoute(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('mrp.group_mrp_manager')
        cls.product = cls.env['product.product'].create({
            'name': 'Calzado recorrido', 'is_storable': True, 'esi_manufacture_ok': True})
        cls.material = cls.env['product.product'].create({
            'name': 'Material recorrido', 'is_storable': True, 'esi_component_ok': True})
        cls.centers = cls.env['mrp.workcenter'].create([
            {'name': name, 'company_id': cls.env.company.id}
            for name in ['Corte', 'Aparado', 'Conformado', 'Solado', 'Terminado']])
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'company_id': cls.env.company.id, 'product_qty': 1,
            'bom_line_ids': [Command.create({'product_id': cls.material.id,
                'product_qty': 2, 'uom_id': cls.material.uom_id.id})],
            'esi_center_route_ids': [Command.create({'sequence': i * 10,
                'workcenter_id': center.id, 'minutes_per_unit': 2})
                for i, center in enumerate(cls.centers, 1)]})

    def _order(self):
        return self.env['mrp.production'].create({'product_id': self.product.id,
            'bom_id': self.bom.id, 'product_qty': 50, 'uom_id': self.product.uom_id.id,
            'company_id': self.env.company.id})

    def test_sequential_full_batch_no_operations_no_stock_until_done(self):
        mo = self._order()
        mo.action_confirm()
        stages = mo.workorder_ids.sorted('esi_center_step')
        self.assertEqual(len(stages), 5)
        self.assertFalse(stages.operation_id)
        self.assertFalse(self.bom.operation_ids)
        self.assertEqual(stages.mapped('state'), ['ready'] + ['blocked'] * 4)
        self.assertEqual(stages.mapped('qty_production'), [50] * 5)
        self.assertEqual(stages.mapped('duration_expected'), [100] * 5)
        with self.assertRaises(UserError):
            stages[1].button_start()
        with self.assertRaises(UserError):
            mo.button_mark_done()
        for stage in stages:
            self.assertEqual(mo.esi_current_center_id, stage.workcenter_id)
            mo.action_esi_start_center()
            mo.action_esi_advance_center()
            self.assertEqual(stage.state, 'done')
            self.assertEqual(stage.qty_produced, 50)
            self.assertFalse(mo.move_finished_ids.filtered(lambda m: m.state == 'done'))
        self.assertFalse(mo.esi_current_center_id)
        self.assertEqual(mo.state, 'to_close')

    def test_duplicate_advance_does_not_skip_next_center(self):
        mo = self._order()
        mo.action_confirm()
        mo.action_esi_start_center()
        mo.action_esi_advance_center()
        with self.assertRaises(UserError):
            mo.action_esi_advance_center()
        self.assertEqual(mo.esi_current_center_id, self.centers[1])
        self.assertEqual(mo.esi_current_center_workorder_id.state, 'ready')

    def test_copy_recipe_and_order_does_not_duplicate_catalog_operations(self):
        copy = self.bom.copy()
        self.assertEqual(copy.esi_center_route_ids.workcenter_id, self.centers)
        self.assertFalse(copy.operation_ids)
        self.assertFalse(set(copy.esi_center_route_ids.ids) & set(self.bom.esi_center_route_ids.ids))

    def test_cannot_reassign_center_or_delete_confirmed_stage(self):
        mo = self._order()
        mo.action_confirm()
        stage = mo.esi_current_center_workorder_id
        with self.assertRaises(UserError):
            stage.workcenter_id = self.centers[1]
        with self.assertRaises(UserError):
            stage.unlink()
        with self.assertRaises(UserError):
            mo.product_qty = 20
        with self.assertRaises(UserError):
            mo._split_productions()

    def test_cannot_combine_recipe_operations_and_center_route(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.bom.write({'operation_ids': [Command.create({'name': 'Corte duplicado',
                'workcenter_id': self.centers[0].id})]})

    def test_wrong_company_center_is_rejected(self):
        other = self.env['res.company'].create({'name': 'Otra fábrica'})
        center = self.env['mrp.workcenter'].create({'name': 'Otro corte', 'company_id': other.id})
        with self.assertRaises((ValidationError, UserError)), self.cr.savepoint():
            self.bom.write({'esi_center_route_ids': [Command.create({'workcenter_id': center.id})]})

    def test_plan_uses_workcenters_without_operations(self):
        mo = self._order()
        mo.action_confirm()
        mo.button_plan()
        self.assertTrue(mo.is_planned)
        self.assertTrue(all(mo.workorder_ids.mapped('leave_id')))
