import ast
import hashlib
import json
from pathlib import Path
import unittest
from lxml import etree

P=Path(__file__).parents[1]
tree=ast.parse((P/'models/recipe_demo.py').read_text())
ns={'hashlib':hashlib}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'demo','exec'),ns)

class DemoRecipeTests(unittest.TestCase):
    def test_source_units_normalized(self):
        for source,target in [('uni','UNIDAD'),('L','LITRO'),('gr','GRAMO'),('ft2','PIE2'),('m','METRO')]:
            self.assertEqual(ns['recipe_unit'](source),target)
    def test_ambiguous_code_never_merges_different_concepts(self):
        a={'code':'ACC-BOL-CEL-35','name':'Bolsa','uom':'uni','unit_price':.35}
        b=dict(a,name='Numeración',unit_price=.19)
        self.assertNotEqual(ns['demo_material_key'](a),ns['demo_material_key'](b))
        self.assertEqual(ns['demo_material_key'](a),ns['demo_material_key'](dict(a)))
    def test_all_twelve_recipes_have_complete_positive_lines(self):
        data=json.loads((P/'data/direct.json').read_text())
        self.assertEqual(len(data['recipes']),12)
        for recipe in data['recipes']:
            lines=[r for r in data['components'] if r['recipe']==recipe['code'] and r['qty_per_pair']>0]
            self.assertTrue(lines,recipe['code'])
            self.assertTrue(all(r['name'] and r['unit_price']>=0 and ns['recipe_unit'](r['uom']) in data['units'] for r in lines))
    def test_only_one_recipe_creation_button(self):
        root=etree.parse(str(P/'views/migration.xml'))
        self.assertEqual(len(root.xpath("//button[@name='action_create_demo_recipes']")),1)
        self.assertFalse(root.xpath("//button[@name='action_create_recipes']"))
    def test_bom_multisize_full_selection_and_centers(self):
        text=(P/'models/recipe_demo.py').read_text()
        self.assertIn("'esi_multi_variant':True",text)
        self.assertIn("'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)]",text)
        self.assertIn("'esi_center_route_ids'",text)
        self.assertIn("['Corte','Aparado','Conformado','Solado','Terminado']",text)
        self.assertNotIn('stock.quant',text)
        self.assertNotIn('action_apply_inventory',text)
