import ast
import json
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
from unittest.mock import MagicMock

P = Path(__file__).parents[1]
D = json.loads((P/'data/direct.json').read_text())
cls = next(n for n in ast.parse((P/'models/direct.py').read_text()).body if isinstance(n, ast.ClassDef))
ns = {'defaultdict':defaultdict, 'UserError':RuntimeError, '_':lambda s:s}
exec(compile(ast.Module(body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_recipe_generated_code','_recipe_material_category','_recipe_create_missing_material','_recipe_find_component','_recipe_qty','_recipe_size_ptav','_recipe_size_rows','_recipes','action_create_recipes')],type_ignores=[]),'recipes','exec'),ns)

class RecipeTests(unittest.TestCase):
    def setup_case(self):
        self.uom=NS(id=2,name='UNIDAD')
        self.template=NS(id=7,uom_id=self.uom,product_variant_ids=NS(ids=[10,11]))
        self.product=NS(id=5,uom_id=self.uom,esi_component_ok=True,standard_price=0,default_code='A',display_name='A')
        self.product.with_company=lambda company:self.product
        self.refs={'mat':self.product,'pt':self.template}
        self.boms=MagicMock()
        self.boms.with_context.return_value=self.boms
        self.boms.with_company.return_value=self.boms
        self.boms.search.return_value=False
        self.obj=NS(env={'mrp.bom':self.boms, 'product.product': MagicMock()},factory_id=NS(id=42,display_name='Fábrica'),
          _ref=lambda k:self.refs.get(k),_uom=lambda u:self.uom,
          _finished_conflict=lambda row:False,_bind=lambda k,v:self.refs.update({k:v}))
        for method in ('_recipe_generated_code','_recipe_material_category','_recipe_create_missing_material',
                       '_recipe_find_component','_recipe_qty','_recipe_size_ptav','_recipe_size_rows'):
            setattr(self.obj, method, MethodType(ns[method], self.obj))
        self.data={'materials':[{'key':'mat','code':'A'}],
          'finished':[{'key':'pt','code':'M-01-NEG'}],
          'recipes':[{'code':'M-01'}],
          'components':[{'recipe':'M-01','code':'A','name':'Cuero','uom':'M2','qty_per_pair':2}]}
    def test_factory_and_repetition(self):
        self.setup_case();notes=[]
        ns['_recipes'](self.obj,self.data,notes)
        values=self.boms.create.call_args.args[0]
        self.assertEqual(values['company_id'],42)
        self.assertEqual(values['product_qty'],1)
        self.assertEqual(values['esi_allowed_variant_ids'],[(6,0,[10,11])])
        self.assertEqual(values['bom_line_ids'][0][2]['product_qty'],2)
        ns['_recipes'](self.obj,self.data,[])
        self.boms.create.assert_called_once()
    def test_incompatible_unit_does_not_create_partial_recipe(self):
        self.setup_case();self.product.uom_id=NS(id=99,name='OTRA');notes=[]
        ns['_recipes'](self.obj,self.data,notes)
        self.boms.create.assert_not_called()
        self.assertIn('sin conversión de unidad',' '.join(notes))
    def test_empty_components_not_created(self):
        self.setup_case();self.data['components']=[]
        ns['_recipes'](self.obj,self.data,[])
        self.boms.create.assert_not_called()
    def test_missing_template_not_created(self):
        self.setup_case();self.data['finished']=[];notes=[]
        ns['_recipes'](self.obj,self.data,notes)
        self.boms.create.assert_not_called()
        self.assertIn('no hay producto terminado',' '.join(notes))
    def test_button_requires_data_and_mrp_permissions(self):
        obj=NS(_lock=lambda:None,data_imported=False)
        with self.assertRaisesRegex(RuntimeError,'Importar datos'):
            ns['action_create_recipes'](obj)
        obj.data_imported=True;obj.env=NS(user=NS(has_group=lambda group:False))
        with self.assertRaisesRegex(RuntimeError,'Fabricación'):
            ns['action_create_recipes'](obj)
    def test_latest_recipe_source_is_used(self):
        src=json.loads((P/'data/recipes_20261028.json').read_text())
        self.assertEqual(D['recipes'],src['recipes'])
        self.assertEqual(D['components'],src['components'])
        self.assertEqual(len(D['recipes']),12)
    def test_negative_opening_is_explicit(self):
        self.assertEqual(D['cutoff'],'2026-10-28')
        rows=[r for r in D['stock'] if r['qty']<0]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['qty'],-18)
        self.assertEqual(D['pending_stock'][0]['code'],'TEX-PEK-18-EST')

if __name__=='__main__':unittest.main()
