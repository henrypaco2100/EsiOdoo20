from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestMigration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.root = self.env['res.company'].create({'name': 'Tosscano prueba raíz'})
        self.branches = self.env['res.company'].create([
            {'name': n, 'parent_id': self.root.id} for n in ['Fábrica prueba', 'CBBA prueba', 'SCZ prueba']])
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=(self.root | self.branches).ids))
        warehouses = self.env['stock.warehouse']
        for idx, branch in enumerate(self.branches):
            existing = warehouses.search([('company_id', '=', branch.id)], limit=1)
            warehouses |= existing or self.env['stock.warehouse'].create({'name': branch.name, 'code': 'TM'+str(idx), 'company_id': branch.id})
        self.migration = self.env['tosscano.migration'].create({
            'root_id': self.root.id, 'factory_id': self.branches[0].id,
            'cbba_id': self.branches[1].id, 'scz_id': self.branches[2].id,
            'warehouse_factory_id': warehouses.filtered(lambda w:w.company_id==self.branches[0])[:1].id,
            'warehouse_cbba_id': warehouses.filtered(lambda w:w.company_id==self.branches[1])[:1].id,
            'warehouse_scz_id': warehouses.filtered(lambda w:w.company_id==self.branches[2])[:1].id})

    def test_load_idempotent(self):
        self.migration.action_load()
        ids = self.migration.line_ids.ids
        self.migration.action_load()
        self.assertEqual(ids, self.migration.line_ids.ids)
        self.assertEqual(len(ids), 1416)

    def test_material_import_scope_idempotent_and_no_stock(self):
        line = self.env['tosscano.migration.line'].create({
            'migration_id': self.migration.id, 'source_key': 'test:1', 'kind': 'material',
            'code': 'TOSSCANO-TEST-ONLY', 'name': 'Prueba', 'family': 'Prueba familia',
            'subfamily': 'Prueba subfamilia', 'reviewed': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id})
        line.action_import_material()
        product = line.product_id
        self.assertEqual(product.company_id, self.branches[0])
        self.assertFalse(product.esi_manufacture_ok)
        self.assertEqual(product.categ_id.parent_id.name, 'Prueba familia')
        line.action_import_material()
        self.assertEqual(line.product_id, product)
        self.assertFalse(self.env['stock.quant'].search([('product_id', '=', product.id)]))

    def test_unreviewed_rejected(self):
        line = self.env['tosscano.migration.line'].create({
            'migration_id': self.migration.id, 'source_key': 'test:2', 'kind': 'material', 'name': 'Sin revisar'})
        with self.assertRaises(UserError):line.action_import_material()
