import importlib.util
import unittest
from pathlib import Path
P=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('classic_hierarchy',P/'models/classic_hierarchy.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def account(code,parent=None,typ='asset_current'):
    return dict(code=code,name=code,type=typ,parent=parent)

class HierarchyTests(unittest.TestCase):
    def test_rollup_includes_parent_postings_once(self):
        accounts={1:account('1'),2:account('11',1),3:account('111',2)}
        rows=h.build_hierarchy(accounts,{2:(10,0,0),3:(20,5,3)})
        self.assertEqual([r['closing'] for r in rows],[32,32,22])
    def test_depth_preserves_rollup(self):
        rows=h.build_hierarchy({1:account('1'),2:account('11',1)},{2:(0,100,0)},max_depth=1)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['amount'],100)
    def test_natural_sign_and_contra_account(self):
        rows=h.build_hierarchy({1:account('1'),2:account('129',1),3:account('2',typ='liability_current')},
            {1:(0,100,0),2:(0,0,20),3:(0,0,80)})
        self.assertEqual([r['amount'] for r in rows],[80,-20,80])
    def test_profit_does_not_add_subtotals_to_result(self):
        rows=h.build_hierarchy({1:account('4',typ='income'),2:account('41',1,'income'),3:account('5',typ='expense')},
            {2:(0,0,300),3:(0,100,0)})
        self.assertEqual([r['amount'] for r in rows],[300,300,100])
    def test_zero_toggle(self):
        accounts={1:account('1')}
        self.assertFalse(h.build_hierarchy(accounts,{}))
        self.assertEqual(len(h.build_hierarchy(accounts,{},show_zero=True)),1)
    def test_configurable_order_within_hierarchy(self):
        rows=h.build_hierarchy({1:account('1'),2:account('11',1),3:account('12',1),4:account('2')},
            {2:(1,0,0),3:(2,0,0),4:(3,0,0)},custom_order={4:1,1:2,3:1,2:2})
        self.assertEqual([r['code'] for r in rows],['2','1','12','11'])
    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):h.build_hierarchy({1:account('1',2),2:account('2',1)},{1:(1,0,0)})
    def test_filters_and_security_contract(self):
        s=(P/'models/classic_report.py').read_text()
        self.assertNotIn('.sudo(',s)
        self.assertIn("('company_id','in',companies.ids)",s)
        self.assertIn("('date','>=',self.date_from)",s)
        self.assertIn("if self.kind == 'balance':\n                    continue",s)
        self.assertIn('assets-liabilities-equity-earnings',s)
        self.assertIn("('id','child_of',self.company_id.id)",s)
