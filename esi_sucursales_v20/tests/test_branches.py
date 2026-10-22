from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestBranchIsolation(TransactionCase):
    """Execute in a disposable Odoo database; these tests require PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = cls.env['res.company'].create({'name': 'Branch test parent'})
        cls.a, cls.b = cls.env['res.company'].create([
            {'name': 'Branch test A', 'parent_id': cls.root.id},
            {'name': 'Branch test B', 'parent_id': cls.root.id},
        ])
        groups = 'base.group_user,sales_team.group_sale_manager,purchase.group_purchase_manager,stock.group_stock_manager,account.group_account_manager'
        cls.user_a = new_test_user(cls.env, login='branch_test_a', groups=groups,
                                  company_id=cls.a.id, company_ids=[Command.set(cls.a.ids)])
        cls.user_ab = new_test_user(cls.env, login='branch_test_ab', groups=groups,
                                   company_id=cls.a.id, company_ids=[Command.set((cls.a | cls.b).ids)])
        partner = cls.env['res.partner'].create({'name': 'Shared test customer'})
        cls.records = {}
        for company in cls.a | cls.b:
            env = cls.env(context=dict(cls.env.context, allowed_company_ids=company.ids))
            cls.records[company.id] = [
                env['sale.order'].create({'partner_id': partner.id, 'company_id': company.id}),
                env['purchase.order'].create({'partner_id': partner.id, 'company_id': company.id}),
                env['account.journal'].create({'name': 'Branch journal', 'code': 'BRT', 'type': 'general', 'company_id': company.id}),
                env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1),
            ]

    def test_single_branch_and_cross_branch_denial(self):
        for own, other in zip(self.records[self.a.id], self.records[self.b.id]):
            self.assertTrue(own and other)
            model = self.env[own._name].with_user(self.user_a).with_context(allowed_company_ids=self.a.ids)
            self.assertTrue(model.search([('id', '=', own.id)]))
            self.assertFalse(model.search([('id', '=', other.id)]))
            with self.assertRaises(AccessError):
                model.browse(other.id).check_access('read')
            with self.assertRaises(AccessError):
                model.browse(other.id).check_access('write')
        order = self.env['sale.order'].with_user(self.user_a).with_context(allowed_company_ids=self.a.ids).new({})
        self.assertEqual(order.company_id, self.a)
        self.assertFalse(order.esi_show_branch)

    def test_authorized_multiple_branches(self):
        model = self.env['sale.order'].with_user(self.user_ab).with_context(allowed_company_ids=(self.a | self.b).ids)
        orders = self.records[self.a.id][0] | self.records[self.b.id][0]
        self.assertEqual(set(model.search([('id', 'in', orders.ids)]).ids), set(orders.ids))
        self.assertTrue(model.new({}).esi_show_branch)

    def test_forged_company_context_rejected(self):
        model = self.env['sale.order'].with_user(self.user_a).with_context(allowed_company_ids=self.b.ids)
        with self.assertRaises(AccessError):
            model.search([])

    def test_parent_journal_not_shared_with_child(self):
        journal = self.env['account.journal'].with_company(self.root).create({
            'name': 'Parent journal', 'code': 'BPAR', 'type': 'general', 'company_id': self.root.id,
        })
        model = self.env['account.journal'].with_user(self.user_a).with_context(allowed_company_ids=self.a.ids)
        self.assertFalse(model.search([('id', '=', journal.id)]))

    def test_selector_only_includes_session_active_branches(self):
        model = self.env['sale.order'].with_user(self.user_ab).with_context(allowed_company_ids=self.a.ids)
        order = model.new({})
        self.assertEqual(order.esi_branch_company_ids, self.a)
        self.assertFalse(order.esi_show_branch)
        self.assertFalse(model.search([('id', '=', self.records[self.b.id][0].id)]))

    def test_selector_shows_multiple_session_active_branches(self):
        model = self.env['sale.order'].with_user(self.user_ab).with_context(allowed_company_ids=(self.a | self.b).ids)
        order = model.new({})
        self.assertEqual(set(order.esi_branch_company_ids.ids), set((self.a | self.b).ids))
        self.assertTrue(order.esi_show_branch)

    def test_journal_list_shows_native_create_button(self):
        """Odoo 20's stock list_no_create class must not suppress Nuevo."""
        base_view = self.env.ref('account.view_account_journal_tree')
        arch, _view = self.env['account.journal']._get_view(
            view_id=base_view.id, view_type='list',
        )
        self.assertEqual(arch.tag, 'list')
        self.assertNotEqual(arch.get('js_class'), 'list_no_create')
        self.assertNotEqual(arch.get('create'), '0')

    def test_journal_kanban_create_opens_standard_form(self):
        """Community must not invoke the missing Enterprise action."""
        base_view = self.env.ref('account.account_journal_view_kanban')
        arch, _view = self.env['account.journal']._get_view(
            view_id=base_view.id, view_type='kanban',
        )
        self.assertEqual(arch.tag, 'kanban')
        self.assertFalse(arch.get('on_create'))
        self.assertEqual(arch.get('quick_create'), 'false')
        self.assertNotEqual(arch.get('create'), '0')

    def test_journal_new_defaults_to_active_company(self):
        """The standard form must respect the active parent or branch."""
        editor = new_test_user(
            self.env,
            login='esi_branch_journal_default_company',
            groups='base.group_user,esi_sucursales_v20.group_esi_journal_editor',
            company_id=self.root.id,
            company_ids=[Command.set((self.root | self.a | self.b).ids)],
        )
        for company in self.root | self.a | self.b:
            model = self.env['account.journal'].with_user(editor).with_context(
                allowed_company_ids=company.ids,
            )
            form_record = model.new({'type': 'general'})
            self.assertEqual(form_record.company_id, company)

    def test_journal_can_be_created_in_parent_and_active_branch(self):
        """A delegated journal editor must be able to create in their current company."""
        editor = new_test_user(
            self.env,
            login='esi_branch_journal_editor',
            groups='base.group_user,esi_sucursales_v20.group_esi_journal_editor',
            company_id=self.root.id,
            company_ids=[Command.set((self.root | self.a | self.b).ids)],
        )
        for idx, company in enumerate((self.root, self.a, self.b)):
            journal_model = self.env['account.journal'].with_user(editor).with_context(
                allowed_company_ids=company.ids,
            )
            journal = journal_model.create({
                'name': f'ESI journal test {idx}',
                'code': f'EJ{idx}',
                'type': 'general',
                'company_id': company.id,
            })
            self.assertEqual(journal.company_id, company)
            self.assertTrue(journal_model.search([('id', '=', journal.id)]))

    def test_journal_editor_cannot_create_outside_authorized_companies(self):
        editor = new_test_user(
            self.env,
            login='esi_branch_restricted_journal_editor',
            groups='base.group_user,esi_sucursales_v20.group_esi_journal_editor',
            company_id=self.a.id,
            company_ids=[Command.set(self.a.ids)],
        )
        model = self.env['account.journal'].with_user(editor).with_context(
            allowed_company_ids=self.a.ids,
        )
        with self.assertRaises(AccessError):
            model.create({
                'name': 'Forbidden sibling journal',
                'code': 'EJB',
                'type': 'general',
                'company_id': self.b.id,
            })
