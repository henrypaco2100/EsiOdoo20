import ast
from pathlib import Path
from types import SimpleNamespace as N
import unittest

class Entries(list):
    def filtered(self, fn): return Entries(m for m in self if fn(m))
    @property
    def ids(self): return [m.id for m in self]
    def check_access(self, operation): pass

class Moves(list):
    def __or__(self, other): return Moves(list(self)+list(other))
    @property
    def account_move_id(self):
        return Entries({m.id:m for m in self if m}.values())

class AccountingTests(unittest.TestCase):
    def test_native_links_count_once_and_scope_company(self):
        source=Path(__file__).parents[1]/'models/production_accounting.py'
        tree=ast.parse(source.read_text()); methods=[]
        for c in tree.body:
            if isinstance(c,ast.ClassDef):
                for n in c.body:
                    if isinstance(n,ast.FunctionDef): n.decorator_list=[];methods.append(n)
        ns={'_':lambda s:s}
        for n in methods:exec(compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),str(source),'exec'),ns)
        company=N(id=7)
        a,b,other=N(id=1,company_id=company),N(id=2,company_id=company),N(id=3,company_id=N(id=8))
        production=N(company_id=company,move_raw_ids=Moves([a]),move_finished_ids=Moves([a,b,other]),
                     ensure_one=lambda:None,check_access=lambda mode:None)
        production._esi_production_account_moves=lambda:ns['_esi_production_account_moves'](production)
        self.assertEqual(production._esi_production_account_moves().ids,[1,2])
        ns['_compute_esi_account_move_count']([production])
        self.assertEqual(production.esi_account_move_count,2)
        action=ns['action_esi_production_account_moves'](production)
        self.assertEqual(action['domain'],[('id','in',[1,2])])
        self.assertFalse(action['context']['create'])
