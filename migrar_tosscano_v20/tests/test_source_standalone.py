"""Pruebas de integridad ejecutables sin instalar Odoo."""
import json
import unittest
from collections import Counter
from pathlib import Path

DATA = json.loads((Path(__file__).parents[1] / 'data/source.json').read_text())

class SourceTests(unittest.TestCase):
    def test_keys_unique(self):
        self.assertEqual(len(DATA), len({r['source_key'] for r in DATA}))
    def test_counts(self):
        self.assertEqual(Counter(r['kind'] for r in DATA), {'material':297,'account':280,'stock':826,'recipe':12,'catalog':1})
    def test_photo_changes_are_row_specific(self):
        rows = {r['source_key']:r for r in DATA}
        self.assertEqual(rows['mp:151']['code'], 'CIN-FT-16-NEG')
        self.assertEqual(rows['mp:154']['code'], 'CIN-FT-09-NEG')
        self.assertEqual(rows['mp:174']['code'], 'CUE-GRL-NEG')
        self.assertEqual(rows['mp:276']['code'], 'HTO-NOR-PL')
        self.assertEqual(json.loads(rows['mp:154']['source_json'])['original']['code'], 'CIN-FT-16-NEG')
    def test_uncertain_thread_duplicate_retained(self):
        self.assertEqual(sum(r['kind']=='material' and r['code']=='HIL-EST-20-CAF' for r in DATA), 2)
    def test_kardex_not_physical_balance(self):
        line = next(r for r in DATA if r['source_key']=='kardex:6')
        self.assertEqual(line['quantity'], 695)
        self.assertEqual(line['branch'], 'FABRICA CALZADO')
    def test_pt_stock_conserved(self):
        totals=Counter()
        for r in DATA:
            if r['source_key'].startswith('ptstock:'):totals[r['branch']]+=r['quantity']
        self.assertEqual(totals, {'FABRICA CALZADO':3840,'CBBA':2141,'SCZ':421})
    def test_recipes_not_lost_or_rescaled(self):
        recipes=[json.loads(r['source_json']) for r in DATA if r['kind']=='recipe']
        self.assertEqual(sum(len(r['components']) for r in recipes),292)
        recipe=next(r for r in recipes if r['recipe']['code']=='M-L-01')
        self.assertEqual(recipe['recipe']['lot'],10)
        self.assertTrue(all('qty_per_pair' in c for c in recipe['components']))
    def test_no_silent_approval(self):
        self.assertTrue(all(not r.get('reviewed') for r in DATA))
        self.assertTrue(all('product_id' not in r for r in DATA))
    def test_evidence_json(self):
        for row in DATA:self.assertIsInstance(json.loads(row['source_json']), dict)

if __name__ == '__main__':unittest.main()
