"""Execute the actual override methods with small ORM doubles (no database)."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

MODELS = Path(__file__).resolve().parents[1] / 'models'


def method(filename, classname, name):
    tree = ast.parse((MODELS / filename).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    return node


class NativeBom:
    def __init__(self, present):
        self.present = present
        self.checked = 0
        self.allowed = True

    def __bool__(self):
        return self.present

    def _esi_check_allowed_products(self, product):
        self.checked += 1
        if not self.present:
            raise ValueError('Expected singleton: mrp.bom()')
        if not self.allowed:
            raise ValueError('Variant forbidden')

    def explode(self, *args):
        return ('native', args)


node = method('bom_variants.py', 'Bom', 'explode')
cls = ast.ClassDef(name='Bom', bases=[ast.Name(id='NativeBom', ctx=ast.Load())],
                   keywords=[], body=[node], decorator_list=[])
ns = {'NativeBom': NativeBom}
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), '<actual explode>', 'exec'), ns)
Bom = ns['Bom']
node = method('production_outputs.py', 'Production', '_onchange_output_recipe')
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<actual onchange>', 'exec'), ns)
onchange = ns['_onchange_output_recipe']


class Lines(list):
    def filtered(self, predicate):
        return Lines(x for x in self if predicate(x))


class TestEmptyBom(unittest.TestCase):
    def test_empty_bom_delegates_to_native(self):
        bom = Bom(False)
        self.assertEqual(bom.explode('product', 1, 'operation', 'excluded'),
                         ('native', ('product', 1, 'operation', 'excluded')))
        self.assertEqual(bom.checked, 0)

    def test_real_bom_keeps_variant_validation(self):
        bom = Bom(True)
        bom.explode('product', 2)
        self.assertEqual(bom.checked, 1)
        bom.allowed = False
        with self.assertRaisesRegex(ValueError, 'Variant forbidden'):
            bom.explode('other product', 2)

    def test_empty_product_delegates(self):
        bom = Bom(True)
        self.assertEqual(bom.explode(False, 1)[0], 'native')
        self.assertEqual(bom.checked, 0)

    def order(self, shared, saved_mode=False):
        return SimpleNamespace(state='draft', esi_group_id=False,
            esi_plan_bom_id=SimpleNamespace(esi_multi_variant=shared, esi_allowed_variant_ids=[10, 20]),
            _origin=SimpleNamespace(esi_variant_line_mode=saved_mode),
            esi_variant_line_mode=False, product_id=10,
            esi_output_line_ids=Lines([SimpleNamespace(product_id=10), SimpleNamespace(product_id=99)]),
            esi_plan_dirty=False)

    def test_shared_recipe_automatically_enables_sizes(self):
        mo = self.order(True)
        onchange(mo)
        self.assertTrue(mo.esi_variant_line_mode)
        self.assertTrue(mo.esi_plan_dirty)
        self.assertEqual([x.product_id for x in mo.esi_output_line_ids], [10])

    def test_recipe_change_keeps_size_mode(self):
        mo = self.order(False)
        mo.esi_variant_line_mode = True
        onchange(mo)
        self.assertTrue(mo.esi_variant_line_mode)

    def test_no_recipe_keeps_sizes_visible(self):
        mo = self.order(False)
        mo.esi_plan_bom_id = False
        onchange(mo)
        self.assertTrue(mo.esi_variant_line_mode)
        self.assertEqual(len(mo.esi_output_line_ids), 2)

    def test_saved_distribution_keeps_mode(self):
        mo = self.order(False, saved_mode=True)
        onchange(mo)
        self.assertTrue(mo.esi_variant_line_mode)

    def test_confirmed_and_group_orders_unchanged(self):
        for state, group in [('confirmed', False), ('draft', True)]:
            mo = self.order(True)
            mo.state, mo.esi_group_id = state, group
            onchange(mo)
            self.assertFalse(mo.esi_variant_line_mode)


if __name__ == '__main__':
    unittest.main()
