import ast
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

P=Path(__file__).parents[1]
tree=ast.parse((P/'models/report_scope.py').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_report_companies','_report_data','_scope_company')]
ns={'UserError':RuntimeError,'_':lambda s,*a:s % a if a else s}
exec(compile(ast.Module(body=methods,type_ignores=[]),'scope','exec'),ns)

class Records(list):
    _fields={'company_id':True}
    @property
    def ids(self):return [c.id for c in self]
    def sorted(self,key):return Records(sorted(self,key=lambda r:getattr(r,key)))
    def check_access(self,operation):pass

class CompanyModel:
    def __init__(self,companies):self.companies=companies
    def with_context(self,**context):return self
    def browse(self,id):return next(c for c in self.companies if c.id==id)
    def search(self,domain):
        root=next(x[2] for x in domain if x[1]=='child_of')
        allowed=next(x[2] for x in domain if x[1]=='in')
        def below(c):
            while c:
                if c.id==root:return True
                c=c.parent
            return False
        return Records(c for c in self.companies if c.id in allowed and below(c))

class Env:
    def __init__(self,companies,assigned):
        self.user=SimpleNamespace(company_ids=Records(assigned))
        self.companies=Records(assigned[:1]) # children need not be checked in session
        self.context={}
        self.model=CompanyModel(companies)
    def __getitem__(self,key):
        if key=='res.company':return self.model
        if key=='stock.warehouse':return SimpleNamespace(search_count=lambda domain: 0 if domain[0][2]==1 else 1)
        raise KeyError(key)

class Report:
    _report_companies=ns['_report_companies']
    _scope_company=ns['_scope_company']
    _report_data=ns['_report_data']
    _name='esi.sales.report'
    _description='Ventas'
    _fields={}
    def __init__(self,env,selected):self.env=env;self.company_id=selected;self.calls=[]
    def ensure_one(self):pass
    def check_access(self,operation):pass
    def __getitem__(self,name):return getattr(self,name)
    def with_context(self,**kw):
        result=copy.copy(self);result.env=copy.copy(self.env)
        result.env.context=dict(self.env.context,**kw)
        return result
    def with_company(self,company):return self.with_context(active_company=company.id)
    def _report_data_single(self):
        c=self._scope_company();self.calls.append(c.id)
        if self._name=='esi.shoe.inventory.report':
            size='39' if c.id==2 else '40'
            return c.name,['Código','Descripción','Unidad','PU','TOTAL',size,'Valor'],[['X','Zapato','PAR',100*c.id,2,2,200*c.id]]
        return c.name,['Documento','Total'],[[str(c.id),10*c.id]]

class ScopeTests(TestCase):
    def setup_tree(self,assigned=(1,2,3,4,9),selected=1):
        currency=SimpleNamespace(name='BOB')
        root=SimpleNamespace(id=1,name='Matriz',parent=None,currency_id=currency)
        a=SimpleNamespace(id=2,name='Fábrica',parent=root,currency_id=currency)
        b=SimpleNamespace(id=3,name='CBBA',parent=root,currency_id=currency)
        sub=SimpleNamespace(id=4,name='Sub CBBA',parent=b,currency_id=currency)
        other=SimpleNamespace(id=9,name='Otra empresa',parent=None,currency_id=currency)
        companies=[root,a,b,sub,other]
        env=Env(companies,[c for c in companies if c.id in assigned])
        return Report(env,next(c for c in companies if c.id==selected))
    def test_matrix_includes_all_authorized_descendants(self):
        r=self.setup_tree();self.assertEqual(r._report_companies().ids,[1,2,3,4])
    def test_branch_does_not_include_siblings_or_parent(self):
        r=self.setup_tree(selected=2);self.assertEqual(r._report_companies().ids,[2])
    def test_intermediate_branch_includes_its_children(self):
        r=self.setup_tree(selected=3);self.assertEqual(r._report_companies().ids,[3,4])
    def test_unassigned_child_excluded(self):
        r=self.setup_tree(assigned=(1,2,9));self.assertEqual(r._report_companies().ids,[1,2])
    def test_unassigned_parent_rejected(self):
        r=self.setup_tree(assigned=(2,),selected=1)
        with self.assertRaises(RuntimeError):r._report_companies()
    def test_forged_effective_company_rejected(self):
        r=self.setup_tree().with_context(esi_report_company_id=9)
        with self.assertRaises(RuntimeError):r._scope_company()
    def test_dispatch_exactly_once_per_authorized_company(self):
        r=self.setup_tree();title,headers,rows=r._report_data()
        self.assertEqual(r.calls,[1,2,3,4]);self.assertEqual(len(rows),4)
        self.assertEqual(headers[0],'Sucursal / compañía')
        self.assertNotIn('Otra empresa',title)
    def test_single_company_keeps_original_columns(self):
        r=self.setup_tree(selected=2);title,headers,rows=r._report_data()
        self.assertEqual(headers,['Documento','Total']);self.assertEqual(rows,[['2',20]])
    def test_matrix_unions_size_columns_and_keeps_company_cost(self):
        r=self.setup_tree(assigned=(1,2,3));r._name='esi.shoe.inventory.report'
        title,h,rows=r._report_data()
        self.assertEqual(r.calls,[2,3]) # no fictitious root warehouse
        self.assertEqual(h,['Sucursal / compañía','Moneda','Código','Descripción','Unidad','PU','TOTAL','39','40','Valor'])
        self.assertEqual(rows[0][5],200);self.assertEqual(rows[1][5],300)
        self.assertEqual(rows[0][7:9],[2,0]);self.assertEqual(rows[1][7:9],[0,2])
    def test_filter_outside_tree_rejected(self):
        r=self.setup_tree();r._fields={'warehouse_id':SimpleNamespace(string='Almacén')}
        other=r.env.model.browse(9)
        r.warehouse_id=Records([SimpleNamespace(id=22,company_id=other)])
        with self.assertRaises(RuntimeError):r._report_data()
    def test_selected_child_warehouse_limits_dispatch(self):
        r=self.setup_tree();r._fields={'warehouse_id':SimpleNamespace(string='Almacén')}
        child=r.env.model.browse(2)
        r.warehouse_id=Records([SimpleNamespace(id=22,company_id=child)])
        r._report_data();self.assertEqual(r.calls,[2])
