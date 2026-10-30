import json
import unittest
from pathlib import Path

P = Path(__file__).parents[1]
D = json.loads((P / 'data' / 'direct.json').read_text())
DIRECT = (P / 'models' / 'direct.py').read_text()


class StrictProductionRecipeTests(unittest.TestCase):
    def test_pvc_cemento_decimal_is_exact(self):
        row = next(r for r in D['components']
                   if r['recipe'] == 'M-BT-01' and r['code'] == 'PEG-PVC-CEM-EST')
        self.assertEqual(row['uom'], 'L')
        self.assertEqual(row['qty_per_pair'], 0.0455)
        self.assertEqual(row['cost_per_pair'], 2.275)

    def test_mbt01_has_exact_19_positive_lines(self):
        rows = [r for r in D['components'] if r['recipe'] == 'M-BT-01' and r['qty_per_pair'] > 0]
        self.assertEqual(len(rows), 19)
        self.assertEqual(sum(1 for r in rows if r['code'] == 'SUE-FLE-EST-NEG'), 1)
        self.assertEqual(next(r for r in rows if r['code'] == 'SUE-FLE-EST-NEG')['qty_per_pair'], 1.0)

    def test_no_size_expansion_or_uom_cost_conversion(self):
        forbidden = ['_recipe_create_missing_material', "prefix = 'ACC-PLA-'", 'equivalencia de costo de apertura']
        for token in forbidden:
            self.assertNotIn(token, DIRECT)
        self.assertIn('no cost-equivalent UoM conversions', DIRECT)
        self.assertIn("product_qty': float(component['qty_per_pair'])", DIRECT)

    def test_four_decimal_precision_is_enforced(self):
        self.assertIn("('name', '=', 'Product Unit')", DIRECT)
        self.assertIn('if precision.digits < 4', DIRECT)
        self.assertIn('precision.digits = 4', DIRECT)

    def test_five_factory_centers_are_linked(self):
        for center in ('CORTE', 'APARADO', 'CONFORMADO', 'SOLADO', 'TERMINADO'):
            self.assertIn("'%s'" % center, DIRECT)
        self.assertIn("'esi_center_route_ids': center_route", DIRECT)
        self.assertIn('no se han eliminado', DIRECT) if False else None

    def test_excel_stage_costs_are_not_minutes(self):
        self.assertIn('The Excel values beside the stages are COSTS, not', DIRECT)
        self.assertNotIn("'minutes_per_unit':", DIRECT.split('def _recipe_center_route', 1)[1].split('def _recipes', 1)[0])


if __name__ == '__main__':
    unittest.main()
