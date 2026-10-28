import ast
import json
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

P = Path(__file__).parents[1]
D = json.loads((P / 'data/direct.json').read_text())
E = json.loads((P / 'data/finished_costs.json').read_text())
tree = ast.parse((P / 'models/direct.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
scope = {'UserError': RuntimeError, '_': lambda s, *a: s % a if a else s,
         'FINISHED_ALIASES': E['aliases']}
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in
           ('_apply_finished_costs', '_ref', '_finished_conflict')]
exec(compile(ast.Module(body=methods, type_ignores=[]), 'finished_costs', 'exec'), scope)

class Records(list):
    def __or__(self, other):
        return Records({r.id: r for r in list(self) + list(other)}.values())
    def with_context(self, **kw):
        return self
    @property
    def product_variant_ids(self):
        return Records(p for t in self for p in t.products)

class FinishedCostsTests(unittest.TestCase):
    def test_complete_positive_coverage(self):
        self.assertEqual(len(E['prices']), 64)
        self.assertEqual(len(D['finished']), 66)
        for row in D['finished']:
            self.assertGreater(row['cost'], 0)
            self.assertEqual(row['cost'], E['prices'][row['code'].removesuffix('-PILOTO')])
            self.assertTrue(row['cost_sources'])

    def test_aliases_and_quantities(self):
        for old, new in E['aliases'].items():
            self.assertFalse(any(r['code'] == old for r in D['finished']))
            self.assertEqual(sum(r['code'] == new for r in D['finished']), 1)
        sums = Counter()
        for row in D['stock']:
            if row['product'].startswith('pt:'):
                sums[row['branch']] += row['qty']
                self.assertGreater(row['cost'], 0)
        self.assertEqual(sums, {'FABRICA CALZADO':3840, 'CBBA':2141, 'SCZ':421})

    def test_no_alias_in_stock_targets(self):
        for row in D['stock']:
            for old in E['aliases']:
                self.assertNotIn('pt:' + old + ':', row['product'])

    def test_all_finished_stock_costs_match_template(self):
        costs = {r['key']:r['cost'] for r in D['finished']}
        for row in D['stock']:
            if row['product'].startswith('pt:'):
                self.assertEqual(row['cost'], costs[row['product'].rsplit(':',1)[0]])

    def test_legacy_balance_reference_is_reused(self):
        product = object()
        m = SimpleNamespace(_exact_ref=lambda key: product if key == 'balance:CBBA:pt:M-W-01-010:40' else False)
        self.assertIs(scope['_ref'](m, 'balance:CBBA:pt:M-W-01-10:40'), product)
        self.assertFalse(scope['_ref'](m, 'balance:CBBA:pt:M-W-01-100:40'))

    def test_existing_duplicate_templates_are_detected(self):
        refs = {'pt:M-W-01-010':SimpleNamespace(id=1), 'pt:M-W-01-10':SimpleNamespace(id=2)}
        m = SimpleNamespace(_exact_ref=refs.get)
        self.assertIn('dos plantillas', scope['_finished_conflict'](m, {'code':'M-W-01-10'}))
        refs['pt:M-W-01-10'] = refs['pt:M-W-01-010']
        self.assertFalse(scope['_finished_conflict'](m, {'code':'M-W-01-10'}))

    def cost_setup(self):
        costs = {i:MagicMock(standard_price=0) for i in range(1,5)}
        for p in costs.values():
            p.write.side_effect = lambda vals, p=p: setattr(p, 'standard_price', vals['standard_price'])
        variant = SimpleNamespace(id=99, with_company=lambda c: costs[c.id])
        template = Records([SimpleNamespace(id=9, products=[variant])])
        refs = {'pt:test':template}
        class Env(dict):
            user = SimpleNamespace(has_group=lambda group: True)
        m = SimpleNamespace(env=Env({'product.template':Records()}),
                            _ref=refs.get, _exact_ref=refs.get,
                            _bind=lambda key, record: refs.update({key:record}))
        for i, field in enumerate(['root_id','factory_id','cbba_id','scz_id'],1):
            setattr(m, field, Records([SimpleNamespace(id=i)]))
        return m, costs, refs

    def test_costs_each_company_native_write_and_repeat_does_not_reset_avco(self):
        m, costs, refs = self.cost_setup()
        data = {'finished':[{'key':'pt:test','code':'test','cost':148.33}]}
        scope['_apply_finished_costs'](m, data)
        for p in costs.values():
            p.write.assert_called_once_with({'standard_price':148.33})
            p.standard_price = 150  # a later receipt changes AVCO
        scope['_apply_finished_costs'](m, data)
        for p in costs.values():
            self.assertEqual(p.standard_price, 150)
            self.assertEqual(p.write.call_count, 1)

    def test_equal_cost_marks_without_revaluation(self):
        m, costs, refs = self.cost_setup()
        for p in costs.values(): p.standard_price = 152
        scope['_apply_finished_costs'](m, {'finished':[{'key':'pt:test','code':'test','cost':152}]})
        for p in costs.values(): p.write.assert_not_called()
        self.assertEqual(len(refs), 5)

    def test_new_price_revision_applies_once(self):
        m, costs, refs = self.cost_setup()
        for cost in (152, 165, 165):
            scope['_apply_finished_costs'](m, {'finished':[{'key':'pt:test','code':'test','cost':cost}]})
        for p in costs.values():
            self.assertEqual(p.standard_price, 165)
            self.assertEqual(p.write.call_count, 2)

if __name__ == '__main__': unittest.main()
