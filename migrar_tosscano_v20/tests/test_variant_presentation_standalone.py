import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path
import unittest
from lxml import etree
P = Path(__file__).parents[1]
S = (P/'models/variant_presentation.py').read_text()
T = ast.parse(S)
class VariantPresentationTests(unittest.TestCase):
    def test_numeric_order(self):
        scope = {'Decimal': Decimal, 'InvalidOperation': InvalidOperation}
        exec(compile(ast.Module(body=[n for n in T.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'<sort>','exec'),scope)
        sort = scope['size_sort_key']
        self.assertEqual(sorted(['40','41','42','34','35','36','37','38','39','43','44','45','46'],key=sort),[str(i) for i in range(34,47)])
        self.assertEqual(sorted(['10','2','9','3,5','S'],key=sort),['2','3,5','9','10','S'])
    def test_repair_sets_native_sequence_and_matrix_without_inventory(self):
        self.assertIn("value.write({'sequence': sequence})",S)
        self.assertIn("template.write({'product_add_mode': 'matrix'})",S)
        for field in ['standard_price','product_qty','action_apply_inventory']:
            self.assertNotIn(field,S)
        view=etree.parse(str(P/'views/migration.xml'))
        self.assertEqual(len(view.xpath("//button[@name='action_fix_size_order_matrix']")),1)
