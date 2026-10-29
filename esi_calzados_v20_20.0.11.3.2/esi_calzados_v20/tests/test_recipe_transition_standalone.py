"""Regression for stale BoM access during the actual template onchange."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

path = Path(__file__).resolve().parents[1] / 'models' / 'production_plan.py'
tree = ast.parse(path.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_onchange_esi_template')
node.decorator_list = []
ns = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), ns)

class Order:
    state = 'draft'
    def __init__(self):
        self.bom_id = 'old restricted recipe'
        self.esi_plan_bom_id = 'old shared recipe'
        self.esi_plan_grid = 'old quantities'
        self._product = SimpleNamespace(product_tmpl_id='old template')
        self.esi_template_id = SimpleNamespace(product_variant_ids=['new variant'])
        self.loaded = False
    @property
    def product_id(self):
        return self._product
    @product_id.setter
    def product_id(self, value):
        if self.bom_id or self.esi_plan_bom_id:
            raise AssertionError('Product assignment still sees stale recipe')
        self._product = value
    def _esi_load_plan_grid(self):
        self.loaded = True

class TestTransition(unittest.TestCase):
    def test_clears_recipes_before_product_triggers(self):
        order = Order()
        ns['_onchange_esi_template'](order)
        self.assertEqual(order.product_id, ['new variant'])
        self.assertFalse(order.esi_plan_grid)
        self.assertTrue(order.loaded)
    def test_confirmed_order_untouched(self):
        order = Order()
        order.state = 'confirmed'
        ns['_onchange_esi_template'](order)
        self.assertEqual(order.bom_id, 'old restricted recipe')
        self.assertFalse(order.loaded)

if __name__ == '__main__':
    unittest.main()
