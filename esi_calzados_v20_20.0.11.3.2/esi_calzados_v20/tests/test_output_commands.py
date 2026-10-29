import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('output_commands', Path(__file__).parents[1] / 'models/output_commands.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
resolve = module.resolve_outputs


class TestOutputCommands(unittest.TestCase):
    def test_three_sizes(self):
        self.assertEqual(resolve({}, [(0, 0, {'product_id': p, 'quantity': q}) for p, q in [(39,20),(40,20),(41,10)]]), [(39,20),(40,20),(41,10)])

    def test_update_and_remove(self):
        self.assertEqual(resolve({10: {'product_id': 39, 'quantity': 20}, 11: {'product_id': 40, 'quantity': 20}},
            [(1, 10, {'quantity': 50}), (2, 11)]), [(39,50)])

    def test_replace_list(self):
        self.assertEqual(resolve({10: {'product_id': 39, 'quantity': 20}},
            [(5,), (0, 0, {'product_id': 41, 'quantity': 10})]), [(41,10)])

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            resolve({}, [(0,0,{'product_id': 39,'quantity': 1}), (0,0,{'product_id': 39,'quantity': 2})])

    def test_reject_foreign_commands(self):
        for command in [(1,99,{'quantity':1}), (2,99), (4,99), (6,0,[99]), (2,'virtual_1162')]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                resolve({10: {'product_id':39,'quantity':20}}, [command])

    def test_reject_reparent(self):
        with self.assertRaises(ValueError):
            resolve({}, [(0,0,{'product_id':39,'quantity':20,'production_id':99})])

    def test_reject_invalid_quantity(self):
        for qty in [0, -1, float('inf'), float('nan'), 'invalid']:
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                resolve({}, [(0,0,{'product_id':39,'quantity':qty})])

    def test_reject_empty(self):
        with self.assertRaises(ValueError):
            resolve({}, [])


if __name__ == '__main__':
    unittest.main()
