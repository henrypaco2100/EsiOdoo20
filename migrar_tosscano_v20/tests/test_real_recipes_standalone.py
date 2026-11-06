import ast
from pathlib import Path
import unittest
from lxml import etree
P=Path(__file__).parents[1]
S=(P/'models/recipe_real.py').read_text()
class RealRecipeTests(unittest.TestCase):
    def test_no_material_or_product_creation(self):
        tree=ast.parse(S)
        self.assertNotIn("env['product.template'].create",S)
        self.assertNotIn("env['product.product'].create",S)
        self.assertNotIn('standard_price',S)
        self.assertNotIn('action_apply_inventory',S)
        self.assertTrue(any(isinstance(n,ast.FunctionDef) and n.name=='action_create_bom' for n in ast.walk(tree)))
    def test_all_variants_and_real_inventory_unit(self):
        self.assertIn("'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)]",S)
        self.assertIn("'uom_id':product.uom_id.id",S)
        self.assertIn("'product_qty':line.inventory_qty_per_pair",S)
    def test_confirmed_quantities_and_numeric_codes(self):
        tree = ast.parse(S)
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in ('name_key', 'code_key')]
        import re, unicodedata
        scope = {'re': re, 'unicodedata': unicodedata}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<matching>', 'exec'), scope)
        self.assertEqual(scope['code_key']('ABC-010'), scope['code_key']('ABC-10'))
        self.assertNotEqual(scope['code_key']('ABC-10'), scope['code_key']('ABC-11'))
        self.assertEqual(scope['name_key']('Termoplástico 0.8'), scope['name_key']('TERMOPLASTICO 08'))
        self.assertIn("quantity = row['qty_per_pair']", S)
        self.assertNotIn('_compute_quantity', S)
        self.assertIn('len(candidates)==1', S)
        self.assertIn('config.action_create_bom()', S)
        self.assertNotIn('if not self.reviewed:', S)
    def test_existing_demo_creation_button_removed(self):
        root=etree.parse(str(P/'views/migration.xml'))
        self.assertFalse(root.xpath("//button[@name='action_create_demo_recipes']"))
        self.assertEqual(len(root.xpath("//button[@name='action_prepare_real_recipes']")),1)
    def test_model_registered_and_no_demo_code_imported(self):
        text=(P/'models/__init__.py').read_text()
        self.assertIn('from . import recipe_real',text)
        self.assertNotIn('from . import recipe_demo',text)
    def test_five_center_route_and_history_protection(self):
        for value in ['Corte','Aparado','Conformado','Solado','Terminado']:self.assertIn(value,S)
        self.assertIn("('bom_id','=',bom.id)",S)
