import ast
import json
import unittest
from pathlib import Path

P = Path(__file__).parents[1]
DIRECT_PATH = P / 'models' / 'direct.py'
DIRECT = DIRECT_PATH.read_text()
DATA = json.loads((P / 'data' / 'direct.json').read_text())

# Extract only the two pure helpers without importing Odoo.
tree = ast.parse(DIRECT)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DirectMigration')
methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in {'_size_sort_key', '_ordered_attribute_values'}]
module = ast.Module(body=methods, type_ignores=[])
ns = {}
exec(compile(module, str(DIRECT_PATH), 'exec'), ns)
size_sort_key = ns['_size_sort_key'].__func__ if isinstance(ns['_size_sort_key'], staticmethod) else ns['_size_sort_key']
ordered_attribute_values = ns['_ordered_attribute_values'].__func__ if isinstance(ns['_ordered_attribute_values'], classmethod) else ns['_ordered_attribute_values']


class Dummy:
    _size_sort_key = staticmethod(size_sort_key)


class SizeOrderAndMatrixTests(unittest.TestCase):
    def test_talla_values_are_numeric_ascending(self):
        values = [40, 41, 42, 34, 35, 36, 39, 38, 37, 46, 44, 45, 43]
        self.assertEqual(
            ordered_attribute_values(Dummy, 'Talla', values),
            [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46],
        )

    def test_talla_duplicates_are_removed(self):
        self.assertEqual(ordered_attribute_values(Dummy, 'Talla', [36, 34, 35, 34]), [34, 35, 36])

    def test_non_size_attribute_preserves_source_order(self):
        self.assertEqual(ordered_attribute_values(Dummy, 'Color', ['NEGRO', 'BEIGE']), ['NEGRO', 'BEIGE'])

    def test_all_finished_source_sizes_are_sorted(self):
        for row in DATA['finished']:
            self.assertEqual(row['sizes'], sorted(row['sizes']), row['code'])

    def test_finished_template_is_created_as_matrix(self):
        self.assertIn("'product_add_mode': 'matrix'", DIRECT)
        self.assertIn("template.product_add_mode != 'matrix'", DIRECT)
        self.assertIn("changed_matrix.write({'product_add_mode': 'matrix'})", DIRECT)

    def test_talla_sequence_is_written(self):
        self.assertIn("vals['sequence'] = int(round(float(str(name_value).replace(',', '.')) * 100))", DIRECT)


if __name__ == '__main__':
    unittest.main()
