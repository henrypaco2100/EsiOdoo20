from odoo import fields, models, _
from odoo.exceptions import UserError

# Source chart references are explicit, not inferred by fuzzy name matching.
ACCOUNT_SPECS = {
    'income': ('4.0.0.01.08', 'Ventas Comerciales', 'income', False),
    'income_factory': ('4.0.0.01.06', 'Ventas - Fabrica', 'income', False),
    'income_cbba': ('4.0.0.01.04', 'Ventas - Tienda Cochabamba', 'income', False),
    'income_scz': ('4.0.0.01.05', 'Ventas - Tienda Santa Cruz', 'income', False),
    'stock_material': ('1.1.3.01.01', 'Materia Prima', 'asset_current', False),
    'stock_other': ('1.1.3.01.02', 'Material Plantas, Otros', 'asset_current', False),
    'stock_finished': ('1.1.3.05.03', 'Productos terminados para venta', 'asset_current', False),
    'expense_material': ('5.0.1.01.01', 'Materia Prima', 'expense_direct_cost', False),
    'expense_other': ('5.0.1.01.02', 'Otros Materiales', 'expense_direct_cost', False),
    'expense_finished': ('5.0.1.01.90', 'Costo de venta de calzados terminados', 'expense_direct_cost', False),
    'variation_material': ('5.0.1.01.91', 'Variación de inventario - Materia prima', 'expense_direct_cost', False),
    'variation_other': ('5.0.1.01.92', 'Variación de inventario - Otros materiales', 'expense_direct_cost', False),
    'variation_finished': ('5.0.1.01.93', 'Variación de inventario - Calzados terminados', 'expense_direct_cost', False),
    'price_difference': ('5.0.1.01.94', 'Diferencias de precio de inventario', 'expense', False),
    'invoices_to_issue': ('1.1.3.99.01', 'Mercadería entregada pendiente de facturar', 'asset_current', True),
    'invoiced_not_delivered': ('2.1.0.99.01', 'Mercadería facturada pendiente de entregar', 'liability_current', True),
    'bills_to_receive': ('2.1.0.99.02', 'Mercadería recibida pendiente de factura', 'liability_current', True),
    'billed_not_received': ('1.1.3.99.02', 'Mercadería facturada pendiente de recibir', 'asset_current', True),
}


def category_values(kind, accounts, journal_id, income_id):
    return {
        'property_cost_method': 'average',
        'property_valuation': 'real_time',
        'property_account_income_categ_id': income_id,
        'property_account_expense_categ_id': accounts['expense_' + kind],
        'property_stock_valuation_account_id': accounts['stock_' + kind],
        'property_stock_journal': journal_id,
        'property_price_difference_account_id': accounts['price_difference'],
        'property_account_invoices_to_issue_id': accounts['invoices_to_issue'],
        'property_account_invoiced_not_delivered_id': accounts['invoiced_not_delivered'],
        'property_account_bills_to_receive_id': accounts['bills_to_receive'],
        'property_account_billed_not_received_id': accounts['billed_not_received'],
    }


class MigrationAccounting(models.Model):
    _inherit = 'tosscano.migration'

    accounting_configured = fields.Boolean(string='Categorías con AVCO y cuentas', readonly=True, copy=False)
    accounting_log = fields.Text(string='Configuración contable aplicada', readonly=True, copy=False)

    def _setup_account(self, role):
        code, name, account_type, reconcile = ACCOUNT_SPECS[role]
        key = 'accounting:' + role
        account = self._ref(key)
        model = self.env['account.account'].with_company(self.root_id).with_context(active_test=False)
        if not account:
            matches = model.search([('code', '=', code), ('company_ids', 'in', self.root_id.ids)])
            compatible = matches.filtered(lambda a: a.active and a.account_type == account_type)
            if len(matches) == 1 and len(compatible) == 1:
                account = compatible
            else:
                named = model.search([('name', '=', name), ('account_type', '=', account_type),
                                      ('active', '=', True), ('company_ids', 'in', self.root_id.ids)])
                if len(named) == 1:
                    account = named
                else:
                    candidate = code
                    suffix = 1
                    while model.search_count([('code', '=', candidate), ('company_ids', 'in', self.root_id.ids)]):
                        candidate = code + '.' + str(suffix).zfill(2)
                        suffix += 1
                    # Attach to the nearest existing chart ancestor when available.
                    parent = self.env['account.account']
                    parts = code.split('.')[:-1]
                    while parts and not parent:
                        candidates = model.search([('code', '=', '.'.join(parts)), ('company_ids', 'in', self.root_id.ids)], limit=2)
                        if len(candidates) == 1:
                            parent = candidates
                        parts.pop()
                    account = model.create({'code': candidate, 'name': name, 'account_type': account_type,
                        'reconcile': reconcile, 'company_ids': [(6, 0, self.root_id.ids)],
                        'parent_id': parent.id if parent else False})
            self._bind(key, account)
        if not account.active or account.account_type != account_type or self.root_id not in account.company_ids:
            raise UserError(_('La cuenta vinculada a %s está archivada o ya no corresponde al tipo/compañía esperado.', role))
        if reconcile and not account.reconcile:
            account.reconcile = True
        return account

    def _stock_journal(self, company):
        journal = company.account_stock_journal_id
        if journal and journal.company_id == company and journal.type == 'general' and journal.active:
            return journal
        key = 'stock_journal:' + str(company.id)
        journal = self._ref(key)
        model = self.env['account.journal'].with_company(company)
        if not journal:
            journal = model.search([('company_id', '=', company.id), ('type', '=', 'general'),
                                   ('name', '=', 'Valoración de inventario Tosscano')], limit=1)
            if not journal:
                code = 'INV'
                number = 1
                while model.with_context(active_test=False).search_count([('company_id', '=', company.id), ('code', '=', code)]):
                    code = 'I%04d' % number
                    number += 1
                journal = model.create({'name': 'Valoración de inventario Tosscano', 'code': code,
                                        'type': 'general', 'company_id': company.id})
            self._bind(key, journal)
        if not journal.active or journal.company_id != company or journal.type != 'general':
            raise UserError(_('Revise el diario de valoración de %s.', company.name))
        company.account_stock_journal_id = journal
        return journal

    def _configure_category_accounting(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Se requieren permisos de administrador de Contabilidad.'))
        data = self._source()
        accounts = {role: self._setup_account(role) for role in ACCOUNT_SPECS}
        # The variation field shown on categories is a related field of the
        # stock account, not an independent company property.
        for kind in ('material', 'other', 'finished'):
            stock = accounts['stock_' + kind]
            vals = {'account_stock_variation_id': accounts['variation_' + kind].id,
                    'account_stock_expense_id': accounts['expense_' + kind].id}
            changes = {k: v for k, v in vals.items() if stock[k].id != v}
            if changes:
                stock.write(changes)
        category_kinds = {}
        for row in data['materials']:
            category = self._category(row.get('family') or 'MATERIAS PRIMAS', row.get('subfamily') or 'OTROS MATERIALES')
            kind = 'material' if (row.get('family') or '').upper() in ('CUEROS', 'TEXTILES', 'MATERIAS PRIMAS') else 'other'
            while category:
                previous = category_kinds.get(category.id)
                category_kinds[category.id] = kind if previous in (None, kind) else 'other'
                category = category.parent_id
        for row in data['finished']:
            category = self._category('CALZADOS ' + row['family'], row['subfamily'], 'Producto terminado')
            while category:
                category_kinds[category.id] = 'finished'
                category = category.parent_id
        # Also cover the actual categories of linked products if recategorized.
        for row in data['materials'] + data['finished']:
            record = self._ref(row['key'])
            if record and record.categ_id.id not in category_kinds:
                category_kinds[record.categ_id.id] = 'finished' if row['key'].startswith('pt:') else 'other'
        ids = {role: account.id for role, account in accounts.items()}
        companies = self.root_id | self.factory_id | self.cbba_id | self.scz_id
        incomes = {self.root_id.id: 'income', self.factory_id.id: 'income_factory',
                   self.cbba_id.id: 'income_cbba', self.scz_id.id: 'income_scz'}
        for company in companies:
            journal = self._stock_journal(company)
            for category_id, kind in category_kinds.items():
                category = self.env['product.category'].browse(category_id).with_company(company)
                vals = category_values(kind, ids, journal.id, ids[incomes[company.id]])
                # Do not trigger native historical AVCO recalculation on repeat.
                changes = {key: value for key, value in vals.items()
                           if (category[key].id if category._fields[key].type == 'many2one' else category[key]) != value}
                if changes:
                    category.write(changes)
        lines = ['AVCO y valoración perpetua configurados en %s categorías, para matriz y tres sucursales.' % len(category_kinds),
                 'Odoo 20 contabiliza compras/ventas al facturar. Las diferencias pendientes se ajustan con la valoración nativa al cierre.',
                 'Se conservan las cuentas específicas existentes en los productos; estas pueden prevalecer sobre la categoría.',
                 'Cuentas compartidas de la matriz:']
        lines += ['%s: %s — %s' % (role, account.with_company(self.root_id).code, account.name) for role, account in accounts.items()]
        self.write({'accounting_configured': True, 'accounting_log': '\n'.join(lines)})

    def action_configure_accounting(self):
        self._lock()
        self._configure_category_accounting()
        return True
