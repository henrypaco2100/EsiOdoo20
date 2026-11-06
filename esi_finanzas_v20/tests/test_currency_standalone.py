import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest
P=Path(__file__).parents[1]
TREE=ast.parse((P/'models/advanced_report.py').read_text())
FUNC=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name=='_advanced_convert')
def translate(message,*args):return message % args if args else message
scope={'UserError':ValueError,'_':translate};exec(compile(ast.Module(body=[FUNC],type_ignores=[]),'<fx>','exec'),scope)
class Currency:
 def __init__(self,id,name,rates=None):self.id=id;self.name=name;self.rates=rates or {};self.calls=[]
 def __or__(self,other):return CurrencySet([self,other])
 def _convert(self,amount,target,company,day,round):
  self.calls.append((company.id,day,target.id,round))
  return amount*self.rates[(company.id,day,target.id)]
class CurrencySet:
 def __init__(self,items):self.items=items
 def __iter__(self):return iter(self.items)
 def _get_rates(self,company,day):return {c.id:(1.,day) for c in self.items if c.id not in getattr(company,'missing',set())}
class CurrencyTests(unittest.TestCase):
 def test_native_conversion_respects_company_date_and_cache(self):
  d=date(2026,10,28);base=Currency(1,'BOB',{(1,d,2):1/7,(2,d,2):1/8});target=Currency(2,'USD');cache={}
  a=SimpleNamespace(id=1,currency_id=base,display_name='Matriz A');b=SimpleNamespace(id=2,currency_id=base,display_name='Matriz B')
  convert=scope['_advanced_convert']
  self.assertAlmostEqual(convert(None,700,a,d,target,cache),100)
  self.assertAlmostEqual(convert(None,350,a,d,target,cache),50)
  self.assertAlmostEqual(convert(None,800,b,d,target,cache),100)
  self.assertEqual(len(base.calls),2);self.assertTrue(all(not call[-1] for call in base.calls))
 def test_same_currency_needs_no_rate(self):
  c=Currency(1,'BOB');co=SimpleNamespace(currency_id=c)
  self.assertEqual(scope['_advanced_convert'](None,50,co,date.today(),c,{}),50)
 def test_missing_foreign_rate_blocks_instead_of_assuming_one(self):
  a=Currency(1,'BOB');b=Currency(2,'USD');co=SimpleNamespace(id=1,currency_id=a,display_name='Matriz',missing={2})
  with self.assertRaises(ValueError):scope['_advanced_convert'](None,700,co,date.today(),b,{})
 def test_sources_keep_full_precision_until_final_presentation(self):
  s=(P/'models/advanced_report.py').read_text()
  self.assertIn('round=False',s);self.assertNotIn('.sudo(',s)
  self.assertIn("line.date>end or (self.kind=='profit' and line.date<start)",s)
  self.assertIn("('company_id','in',companies.ids)",s)
  self.assertIn("('parent_state','!=','cancel')",s)
 def test_trial_comparison_uses_raw_closing_balance(self):
  s=(P/'models/advanced_report.py').read_text();self.assertIn("for row in rows:row['amount']=row['closing']",s)
 def test_full_entry_matching_precedes_selected_account_filter(self):
  s=(P/'models/advanced_report.py').read_text();self.assertIn('entry_domain=list(domain)',s)
  self.assertIn('search(entry_domain',s)
