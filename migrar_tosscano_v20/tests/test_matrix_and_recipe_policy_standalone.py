import json
import unittest
from pathlib import Path

P = Path(__file__).parents[1]
DIRECT = (P / 'models' / 'direct.py').read_text()
DATA = json.loads((P / 'data' / 'direct.json').read_text())

class MatrixAndRecipePolicyTests(unittest.TestCase):
    def test_finished_templates_default_to_matrix(self):
        self.assertIn("'product_add_mode': 'matrix'", DIRECT)
        self.assertIn("template.product_add_mode != 'matrix'", DIRECT)
        self.assertIn("changed_matrix = finished_templates.filtered", DIRECT)
        self.assertIn("changed_matrix.write({'product_add_mode': 'matrix'})", DIRECT)

    def test_recipe_policy_is_strict_excel(self):
        self.assertIn('exact component code', DIRECT)
        self.assertIn('no size-dependent substitutions', DIRECT)
        self.assertIn('no creation of missing materials', DIRECT)
        self.assertIn('no cost-equivalent UoM conversions', DIRECT)

    def test_recipe_targets_known_from_current_finished_catalog(self):
        no_target=[]
        for recipe in DATA['recipes']:
            if not any(row['code'].startswith(recipe['code'] + '-') for row in DATA['finished']):
                no_target.append(recipe['code'])
        self.assertEqual(no_target, ['M-BT-03', 'M-L-00', 'M-P-02'])

    def test_attached_recipe_source_has_twelve_models(self):
        self.assertEqual(len(DATA['recipes']), 12)
        self.assertEqual(len(DATA['components']), 290)

if __name__ == '__main__': unittest.main()
