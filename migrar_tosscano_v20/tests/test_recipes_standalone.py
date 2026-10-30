import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
from unittest.mock import MagicMock

P = Path(__file__).parents[1]
D = json.loads((P/'data/direct.json').read_text())
SRC = json.loads((P/'data/recipes_20261030.json').read_text())
DIRECT = (P/'models/direct.py').read_text()

class RecipeSourceTests(unittest.TestCase):
    def test_authoritative_source_is_loaded_exactly(self):
        self.assertEqual(D['recipes'], SRC['recipes'])
        self.assertEqual(D['components'], SRC['components'])
        self.assertEqual(len(D['recipes']), 12)
        self.assertEqual(len(D['components']), 290)
        self.assertEqual(sum(1 for r in D['components'] if float(r.get('qty_per_pair') or 0) > 0), 288)

    def test_mbt01_matches_approved_sheet(self):
        rows=[r for r in D['components'] if r['recipe']=='M-BT-01' and r['qty_per_pair']>0]
        self.assertEqual(len(rows),19)
        first=rows[0]
        self.assertEqual((first['code'], first['name'], first['uom'], first['qty_per_pair']),
                         ('PEG-ALO-EST-EST','ALOGENANTE (caja de 24)','L',0.012))
        plant=next(r for r in rows if r['code']=='SUE-FLE-EST-NEG')
        self.assertEqual((plant['name'],plant['uom'],plant['qty_per_pair']),('PLANTA FLEXSOLE','uni',1.0))
        plantilla=next(r for r in rows if r['code']=='ACC-PLA-40')
        self.assertEqual((plantilla['name'],plantilla['uom'],plantilla['qty_per_pair']),('PLANTILLAS','par',1.0))

    def test_no_size_substitution_or_cost_conversion_logic(self):
        self.assertNotIn("ACC-ETQ-BOL-MIL-", DIRECT)
        self.assertNotIn("prefix = 'ACC-PLA-'", DIRECT)
        self.assertNotIn('equivalencia de costo de apertura', DIRECT)
        self.assertNotIn('_recipe_create_missing_material', DIRECT)
        self.assertIn('_recipe_find_component_exact', DIRECT)
        self.assertIn('NO CREADA. Corrija primero estas diferencias', DIRECT)

    def test_zero_quantity_rows_remain_evidence_but_not_positive(self):
        zero=[r for r in D['components'] if float(r.get('qty_per_pair') or 0)==0]
        self.assertEqual(len(zero),2)
        self.assertEqual({r['code'] for r in zero},{'ACC-BAN-BRA-EST','ACC-CIE-EST-COY-06'})

    def test_negative_opening_is_explicit(self):
        self.assertEqual(D['cutoff'],'2026-10-28')
        rows=[r for r in D['stock'] if r['qty']<0]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['qty'],-18)
        self.assertEqual(D['pending_stock'][0]['code'],'TEX-PEK-18-EST')

if __name__=='__main__': unittest.main()
