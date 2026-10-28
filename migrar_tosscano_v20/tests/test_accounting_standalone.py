import ast
from pathlib import Path
import unittest

P=Path(__file__).parents[1]
T=ast.parse((P/'models/accounting_setup.py').read_text())
namespace={}
selected=[n for n in T.body if isinstance(n,ast.FunctionDef) or isinstance(n,ast.Assign)]
exec(compile(ast.Module(body=selected,type_ignores=[]),'accounting_setup','exec'),namespace)
SPECS=namespace['ACCOUNT_SPECS']
VALUES=namespace['category_values']

class AccountingTests(unittest.TestCase):
    def test_each_category_kind_avco_perpetual(self):
        accounts={name:i+1 for i,name in enumerate(SPECS)}
        for kind in ('material','other','finished'):
            vals=VALUES(kind,accounts,42,99)
            self.assertEqual(vals['property_cost_method'],'average')
            self.assertEqual(vals['property_valuation'],'real_time')
            self.assertEqual(vals['property_stock_journal'],42)
            self.assertEqual(vals['property_account_income_categ_id'],99)
            self.assertEqual(vals['property_stock_valuation_account_id'],accounts['stock_'+kind])
            self.assertEqual(vals['property_account_expense_categ_id'],accounts['expense_'+kind])
    def test_all_four_transitory_accounts_set(self):
        accounts={name:i+1 for i,name in enumerate(SPECS)}
        vals=VALUES('finished',accounts,1,2)
        for role in ('invoices_to_issue','invoiced_not_delivered','bills_to_receive','billed_not_received'):
            self.assertEqual(vals['property_account_'+role+'_id'],accounts[role])
            self.assertTrue(SPECS[role][3])
    def test_asset_liability_direction(self):
        for role in ('invoices_to_issue','billed_not_received'):
            self.assertEqual(SPECS[role][2],'asset_current')
        for role in ('invoiced_not_delivered','bills_to_receive'):
            self.assertEqual(SPECS[role][2],'liability_current')
    def test_chart_codes_do_not_collide(self):
        codes=[r[0] for r in SPECS.values()]
        self.assertEqual(len(codes),len(set(codes)))
    def test_variation_and_cogs_are_different(self):
        for kind in ('material','other','finished'):
            self.assertNotEqual(SPECS['variation_'+kind][0],SPECS['expense_'+kind][0])
            self.assertEqual(SPECS['stock_'+kind][2],'asset_current')
    def test_branch_income_codes(self):
        self.assertEqual(SPECS['income_factory'][0],'4.0.0.01.06')
        self.assertEqual(SPECS['income_cbba'][0],'4.0.0.01.04')
        self.assertEqual(SPECS['income_scz'][0],'4.0.0.01.05')

if __name__=='__main__':unittest.main()
