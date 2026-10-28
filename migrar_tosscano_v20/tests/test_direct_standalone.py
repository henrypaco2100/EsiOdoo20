import ast
import json
import unittest
from collections import Counter
from pathlib import Path
P=Path(__file__).parents[1]
D=json.loads((P/'data/direct.json').read_text())

class DirectDataTests(unittest.TestCase):
    def test_unique_material_codes_and_keys(self):
        for field in ['key','code']:
            self.assertEqual(len(D['materials']),len({r[field] for r in D['materials']}))
    def test_every_stock_target_exists(self):
        keys={r['key'] for r in D['materials']}
        keys.update(r['key']+':'+str(size) for r in D['finished'] for size in r['sizes'])
        self.assertTrue(all(r['product'] in keys for r in D['stock']))
    def test_finished_conservation_per_branch(self):
        sums=Counter()
        for r in D['stock']:
            if r['product'].startswith('pt:'):sums[r['branch']]+=r['qty']
        self.assertEqual(sums,{'FABRICA CALZADO':3840,'CBBA':2141,'SCZ':421})
    def test_variant_combinations_unique(self):
        codes=[r['code']+'-T'+str(s) for r in D['finished'] for s in r['sizes']]
        self.assertEqual(len(codes),len(set(codes)))
        self.assertEqual(len(codes),352)
    def test_pilot_separated(self):
        r=[v for v in D['finished'] if v['key'].startswith('pt:M-L-01-03-00')]
        self.assertEqual(len(r),2)
        self.assertEqual(len({v['code'] for v in r}),2)
    def test_units_and_categories_complete(self):
        self.assertEqual(set(D['units']),{'BOTE','CONO','GRAMO','KG','LATA','LITRO','M2','METRO','PAQUETE','PAR','PIE2','ROLLO','UNIDAD'})
        for r in D['materials']:
            self.assertTrue(r['family']);self.assertTrue(r['subfamily']);self.assertIn(r['uom'],D['units'])
    def test_account_parents_and_types(self):
        ids={r['id'] for r in D['accounts']}
        self.assertEqual(len(ids),280)
        self.assertTrue(all(not r['parent'] or r['parent'] in ids for r in D['accounts']))
    def test_no_rewrite_native_dates(self):
        tree=ast.parse((P/'models/direct.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='action_apply_inventory']
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0].args or calls[0].keywords)
    def test_global_identity_survives_module_uninstall(self):
        source=(P/'models/direct.py').read_text()
        self.assertIn("'module': 'tosscano_import_data'",source)
        self.assertIn('self._bind(mark,product)',source)

if __name__=='__main__':unittest.main()
