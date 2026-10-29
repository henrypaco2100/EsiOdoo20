import ast
import importlib.util
import json
from pathlib import Path
import unittest

P=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('size_policy',P/'models/size_policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
D=json.loads((P/'data/direct.json').read_text())

class SizesTests(unittest.TestCase):
    def test_all_adult_templates_have_complete_range(self):
        adult=[r for r in D['finished'] if not policy.is_children_line(r)]
        self.assertEqual(len(adult),58)
        for row in adult:self.assertTrue(set(range(34,47)).issubset(row['sizes']),row['code'])
    def test_children_not_extended(self):
        for family in ['ESCOLAR','INFANTIL']:
            row={'family':family,'sizes':[27,30,34]}
            self.assertEqual(policy.required_sizes(row),[27,30,34])
    def test_preserves_other_sizes_and_is_idempotent(self):
        row={'family':'MILITAR','sizes':[33,40,47]}
        first=policy.required_sizes(row)
        self.assertEqual(first,list(range(33,48)))
        row['sizes']=first
        self.assertEqual(policy.required_sizes(row),first)
    def test_completion_never_calls_stock_import(self):
        tree=ast.parse((P/'models/direct.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='action_complete_sizes')
        attrs=[n.func.attr for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertIn('_finished',attrs)
        self.assertIn('_apply_finished_costs',attrs)
        self.assertNotIn('action_import_stock',attrs)
        self.assertNotIn('action_apply_inventory',attrs)
    def test_variant_total(self):
        self.assertEqual(sum(len(r['sizes']) for r in D['finished']),802)
