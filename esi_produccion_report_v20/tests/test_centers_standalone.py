import ast
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest
T=ast.parse((Path(__file__).parents[1]/'models/main.py').read_text())
C=next(c for c in T.body if isinstance(c,ast.ClassDef) and c.name=='Report')
ns={}
exec(compile(ast.Module(body=[n for n in C.body if isinstance(n,ast.FunctionDef) and n.name in ('_esi_current_workorders','_esi_operation_summary')],type_ignores=[]),'report','exec'),ns)
class Rows(list):
    def sorted(self,key):return Rows(sorted(self,key=key))
    def filtered(self,fn):return Rows(r for r in self if fn(r))
    def __getitem__(self,k):
        v=super().__getitem__(k)
        return Rows(v) if isinstance(k,slice) else v
    _fields={'state':Obj(_description_selection=lambda env:[('progress','En progreso'),('ready','Lista'),('pending','Pendiente')])}
def wo(i,state,center='Corte'):
    return Obj(id=i,sequence=i,state=state,name='Operación con otro nombre',workcenter_id=Obj(name=center),_fields={'sequence':True})
class Centers(unittest.TestCase):
    def setUp(self):
        self.report=Obj(env=None)
        self.report._esi_current_workorders=lambda order:ns['_esi_current_workorders'](self.report,order)
    def current(self,rows,state='progress'):
        return self.report._esi_current_workorders(Obj(workorder_ids=Rows(rows),state=state))
    def test_progress_precedes_ready(self):self.assertEqual([w.id for w in self.current([wo(1,'ready'),wo(2,'progress')])],[2])
    def test_parallel_centers_preserved(self):self.assertEqual(len(self.current([wo(1,'progress'),wo(2,'progress')])),2)
    def test_next_ready_after_completed(self):self.assertEqual([w.id for w in self.current([wo(1,'done'),wo(2,'ready')])],[2])
    def test_first_pending(self):self.assertEqual([w.id for w in self.current([wo(2,'pending'),wo(1,'pending')])],[1])
    def test_closed_has_no_active_center(self):
        for state in ('done','cancel'):self.assertFalse(self.current([wo(1,'progress')],state))
    def test_no_workorders(self):self.assertFalse(self.current([]))
    def test_summary_uses_center_not_operation(self):
        order=Obj(workorder_ids=Rows([wo(1,'progress','Aparado')]),state='progress')
        self.assertEqual(ns['_esi_operation_summary'](self.report,order),('Aparado','En progreso','0/1'))
if __name__=='__main__':unittest.main()
