from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMaterialRequest(TransactionCase):
    def test_draft_without_vendor_and_confirmation_guard(self):
        order = self.env['purchase.order'].create({'esi_material_request': True})
        self.assertFalse(order.partner_id)
        self.assertEqual(order.state, 'draft')
        for action in (order.button_confirm, order.button_approve, order.action_rfq_send):
            with self.assertRaises(UserError):
                action()
        order.button_cancel()
        self.assertEqual(order.state, 'cancel')

    def test_normal_purchase_still_requires_vendor(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['purchase.order'].create({})

    def test_select_vendor_after_draft_keeps_lines(self):
        product = self.env['product.product'].create({'name': 'Material pendiente', 'purchase_ok': True})
        order = self.env['purchase.order'].create({'esi_material_request': True,
            'order_line': [Command.create({'product_id': product.id, 'product_qty': 45, 'uom_id': product.uom_id.id})]})
        line_id = order.order_line.id
        self.assertFalse(order.order_line._get_seller_info())
        supplier = self.env['res.partner'].create({'name': 'Proveedor asignado después', 'supplier_rank': 1})
        order.partner_id = supplier
        self.assertEqual(order.order_line.id, line_id)
        self.assertEqual(order.order_line.product_qty, 45)
        order._esi_require_vendor()

    def test_direct_state_change_without_vendor_is_rejected(self):
        order = self.env['purchase.order'].create({'esi_material_request': True})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.state = 'purchase'
