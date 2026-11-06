import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('layout_engine',P/'models/layout_engine.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
A={1:dict(code='4',name='INGRESOS',type='income',parent=None),2:dict(code='41',name='VENTAS',type='income',parent=1),3:dict(code='5',name='COSTOS',type='expense_direct_cost',parent=None),4:dict(code='6',name='GASTOS',type='expense',parent=None)}
F=[dict(account=2,journal=1,values=(0.,0.,300.,-300.)),dict(account=3,journal=1,values=(0.,100.,0.,100.)),dict(account=4,journal=2,values=(0.,50.,0.,50.))]
def node(name,mode='account_type',**kw):
 d=dict(name=name,mode=mode,sign='1',detail='none',visible=True,parent=False);d.update(kw);return d
class LayoutTests(unittest.TestCase):
 def test_types_and_formula_use_presented_balances_once(self):
  nodes={1:node('INGRESOS',types=['income'],sign='-1'),2:node('COSTOS',types=['expense_direct_cost']),3:node('GASTOS',types=['expense']),4:node('RESULTADO','formula',terms=[(1,1),(2,-1),(3,-1)])}
  r=e.evaluate_layout(nodes,[1,2,3,4],F,A)
  self.assertEqual([x['amount'] for x in r],[300,100,50,150]);self.assertEqual(r[0]['credit'],300)
 def test_account_selection_includes_children(self):
  r=e.evaluate_layout({1:node('V','accounts',accounts=[1],include_children=True)},[1],F,A)
  self.assertEqual(r[0]['amount'],-300)
 def test_reference(self):
  r=e.evaluate_layout({1:node('V',types=['income']),2:node('R','reference',reference=1,sign='-1')},[2],F,A)
  self.assertEqual(r[0]['amount'],300)
 def test_reference_cycle(self):
  with self.assertRaises(ValueError):e.evaluate_layout({1:node('A','reference',reference=2),2:node('B','reference',reference=1)},[1],F,A)
 def test_excluded_journal_inherited_and_printed_consistently(self):
  nodes={1:node('TOTAL','sum',excluded=[2]),2:node('GASTOS',types=['expense'],parent=1)}
  self.assertFalse(e.evaluate_layout(nodes,[1],F,A))
  r=e.evaluate_layout(nodes,[1],F,A,display='all');self.assertEqual([x['amount'] for x in r],[0,0])
 def test_hidden_helpers_still_feed_formula(self):
  r=e.evaluate_layout({1:node('V',types=['income'],sign='-1',visible=False),2:node('R','formula',terms=[(1,1)])},[1,2],F,A)
  self.assertEqual(len(r),1);self.assertEqual(r[0]['amount'],300)
 def test_zero_and_movement_filters(self):
  f=[dict(account=2,journal=1,values=(0.,10.,10.,0.))]
  n={1:node('V',types=['income'])}
  self.assertEqual(len(e.evaluate_layout(n,[1],f,A)),1)
  self.assertFalse(e.evaluate_layout(n,[1],f,A,display='not_zero'))
 def test_numeric_sequence_and_code_order(self):
  n={1:node('B',code='2',sequence=1,types=['income']),2:node('A',code='1',sequence=2,types=['expense'])}
  self.assertEqual([x['name'] for x in e.evaluate_layout(n,[1,2],F,A)],['B','A'])
  self.assertEqual([x['name'] for x in e.evaluate_layout(n,[1,2],F,A,order='code')],['A','B'])
 def test_analytic_composite_key_not_double_counted(self):
  self.assertEqual(e.analytic_weight({'1,2':60,'3,2':40},{1,2}),1.)
  self.assertEqual(e.analytic_weight({'1,2':60,'3,2':40},{1}),.6)
 def test_analytic_empty_and_unmatched(self):
  self.assertEqual(e.analytic_weight({},set()),1.)
  self.assertEqual(e.analytic_weight({'1':100},{2}),0.)
 def test_detail_rollup_no_double_count(self):
  n={1:node('VENTAS',types=['income'],sign='-1',detail='hierarchy')}
  rows=e.evaluate_layout(n,[1],F,A)
  self.assertEqual([r['amount'] for r in rows],[300,300,300])
 def test_standard_title_does_not_repeat_same_root_account(self):
  nodes={1:node('INGRESOS',code='4',types=['income'],sign='-1',detail='hierarchy')}
  rows=e.evaluate_layout(nodes,[1],F,A)
  self.assertEqual([r['code'] for r in rows],['4','41'])
  self.assertEqual([r['depth'] for r in rows],[1,2])
 def test_missing_reference_fails(self):
  with self.assertRaises(ValueError):e.evaluate_layout({1:node('A','reference',reference=999)},[1],F,A)

class CashFlowTests(unittest.TestCase):
 def test_category_subtotals_and_ending_do_not_double_count(self):
  groups={1:dict(name='INGRESOS',parent=None),2:dict(name='VENTAS',parent=1),3:dict(name='GASTOS',parent=None)}
  facts=[dict(group=2,opening=True,values=(500.,0.,0.,500.)),dict(group=2,opening=False,values=(0.,100.,0.,100.)),dict(group=3,opening=False,values=(0.,0.,50.,-50.))]
  rows=e.cashflow_rows(facts,groups)
  values={r['key']:r['amount'] for r in rows}
  self.assertEqual(values['flow:1'],100);self.assertEqual(values['flow:2'],100)
  self.assertEqual(values['flow:change'],50);self.assertEqual(values['flow:ending'],550)
 def test_flow_cycle_rejected(self):
  with self.assertRaises(ValueError):e.cashflow_rows([], {1:dict(name='A',parent=2),2:dict(name='B',parent=1)})
