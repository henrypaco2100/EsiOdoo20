import ast
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from test_layout_engine_standalone import e
P=Path(__file__).parents[1]
T=ast.parse((P/'models/layout.py').read_text())
TYPES=ast.literal_eval(next(n.value for n in T.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ACCOUNT_TYPES' for t in n.targets)))
FN=next(n for n in ast.walk(T) if isinstance(n,ast.FunctionDef) and n.name=='action_create_standard')
S={'ValidationError':ValueError,'_':lambda x,*a:x%a if a else x,'ACCOUNT_TYPES':TYPES};exec(compile(ast.Module(body=[FN],type_ignores=[]),'<standard>','exec'),S)
class Records(list):
 @property
 def ids(self):return [r.id for r in self]
class Store:
 def __init__(self):self.records=[]
 def create(self,values):
  rec=N(id=len(self.records)+1,**values);self.records.append(rec);return rec
 def search(self,domain):
  def matches(r):
   for field,op,value in domain:
    actual=getattr(r,field,None)
    if op=='=' and actual!=value:return False
    if op=='in' and actual not in value:return False
   return True
  return Records(r for r in self.records if matches(r))
 def search_count(self,domain):return len(self.search(domain))
class Env:
 company=N(id=1)
 user=N(has_group=lambda group:True)
 def __init__(self):self.types=Store();self.lines=Store()
 def __getitem__(self,name):return self.types if name=='esi.finance.account.type' else self.lines
class LayoutStore(Store):
 _name='esi.finance.layout'
 def __init__(self):super().__init__();self.env=Env()
class StandardTests(unittest.TestCase):
 def test_standard_creation_is_idempotent(self):
  store=LayoutStore();S['action_create_standard'](store);S['action_create_standard'](store)
  self.assertEqual(len(store.records),2);self.assertEqual(len(store.env.lines.records),12)
 def test_standard_profit_and_balance_reconcile(self):
  store=LayoutStore();S['action_create_standard'](store)
  type_by_id={r.id:r.code for r in store.env.types.records}
  accounts={1:dict(code='1',name='A',type='asset_cash',parent=None),2:dict(code='2',name='L',type='liability_current',parent=None),3:dict(code='3',name='E',type='equity',parent=None),4:dict(code='4',name='I',type='income',parent=None),5:dict(code='5',name='G',type='expense',parent=None)}
  # Balanced journal facts: 100 debit asset + 70 debit expense = 40 liability + 30 equity + 100 income.
  facts=[dict(account=aid,journal=1,values=(0.,max(value,0),max(-value,0),value)) for aid,value in [(1,100),(2,-40),(3,-30),(4,-100),(5,70)]]
  for layout in store.records:
   nodes={}
   for line in store.env.lines.records:
    if line.layout_id!=layout.id:continue
    v=vars(line)
    nodes[line.id]=dict(name=line.name,code=line.code,sequence=line.sequence,parent=False,mode=line.mode,detail=v.get('detail','none'),sign=v.get('sign','1'),visible=v.get('visible',True),
      types=[type_by_id[x] for x in v.get('account_type_ids',[(6,0,[])])[0][2]],terms=[(term[2]['source_id'],int(term[2]['operation'])) for term in v.get('term_ids',[])])
   rows=e.evaluate_layout(nodes,list(nodes),facts,accounts)
   amounts={row['code']:row['amount'] for row in rows}
   if layout.kind=='profit':self.assertEqual(amounts['R'],30)
   else:
    self.assertEqual(amounts['1'],100);self.assertEqual(amounts['PP'],100);self.assertEqual(amounts['D'],0)
