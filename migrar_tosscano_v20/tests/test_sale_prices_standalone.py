import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
import unittest
P=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('price_mapping',P/'models/price_mapping.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
D=json.loads((P/'data/direct.json').read_text())
S=json.loads((P/'data/sale_prices.json').read_text())
cls=next(n for n in ast.parse((P/'models/sale_prices.py').read_text()).body if isinstance(n,ast.ClassDef))
ns={'resolve_prices':m.resolve_prices,'UserError':RuntimeError,'_':lambda s,*a:s%a if a else s}
exec(compile(ast.Module(body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_import_sale_prices'],type_ignores=[]),'sale_prices','exec'),ns)

class SalePriceTests(unittest.TestCase):
    def test_coverage_and_unmatched_code(self):
        plan,missing,unused=m.resolve_prices(D['finished'],S)
        self.assertEqual(len(S['rows']),77)
        self.assertEqual(len(plan),65)
        self.assertEqual(missing,['EL-V-02-06'])
        self.assertIn('E-V-02',unused)
    def test_pilot_and_all_size_templates_follow_model(self):
        plan,_,_=m.resolve_prices(D['finished'],S)
        rows=[r for r in plan if r['source_code']=='M-L-01']
        self.assertTrue(any('PILOTO' in r['code'] for r in rows))
        self.assertTrue(all(r['retail']==330 and r['wholesale']==340 for r in rows))
    def test_blank_wholesale_falls_back_not_zero(self):
        plan,_,_=m.resolve_prices(D['finished'],S)
        row=next(r for r in plan if r['code']=='C-CLK-01-01')
        self.assertEqual((row['retail'],row['wholesale']),(220,220))
        self.assertTrue(row['wholesale_fallback'])
    def test_longest_delimited_match(self):
        src={'rows':[{'code':'X-1','retail':10,'wholesale':None,'row':1}, {'code':'X-10','retail':20,'wholesale':15,'row':2}]}
        plan,missing,_=m.resolve_prices([{'key':'a','code':'X-10-B'},{'key':'b','code':'X-100-B'}],src)
        self.assertEqual(plan[0]['retail'],20)
        self.assertEqual(missing,['X-100-B'])
    def test_invalid_prices_rejected(self):
        for value in [0,-1,'',float('nan')]:
            with self.assertRaises(ValueError):m.resolve_prices([],{'rows':[{'code':'A','retail':value,'wholesale':None}]})
    def test_import_rules_and_idempotence_preserve_manual_edits(self):
        template=MagicMock();template.id=10;template.company_id=False
        refs={'pt:A':template}
        retail=NS(id=20);wholesale=NS(id=21)
        feature=object();internal=NS(implied_ids=[feature])
        item_model=MagicMock();item_model.create.side_effect=lambda v:NS(id=len(refs),pricelist_id=retail if v['pricelist_id']==20 else wholesale,product_tmpl_id=template)
        env=MagicMock();env.user.has_group.return_value=True
        env.ref.side_effect=lambda key:feature if key=='product.group_product_pricelist' else internal
        env.__getitem__.return_value=item_model
        obj=NS(env=env,ensure_one=lambda:None,_sale_price_source=lambda:{'revision':'2026-10-29','rows':[{'code':'A','retail':220,'wholesale':150,'row':7}]},
            _sale_pricelist=lambda k,l:retail if k=='retail' else wholesale,_finished_conflict=lambda row:False,
            _ref=lambda k:refs.get(k),_bind=lambda k,v:refs.update({k:v}),write=MagicMock())
        data={'finished':[{'key':'pt:A','code':'A-NEG'}]}
        ns['_import_sale_prices'](obj,data)
        template.write.assert_called_once_with({'list_price':220})
        self.assertEqual(item_model.create.call_count,2)
        values=[call.args[0] for call in item_model.create.call_args_list]
        self.assertEqual([v['fixed_price'] for v in values],[220,150])
        self.assertTrue(all(v['product_tmpl_id']==10 and v['product_id'] is False and v['min_quantity']==0 for v in values))
        template.write.reset_mock();item_model.create.reset_mock()
        ns['_import_sale_prices'](obj,data)
        template.write.assert_not_called();item_model.create.assert_not_called()
    def test_only_sales_price_fields_written(self):
        text=(P/'models/sale_prices.py').read_text()
        self.assertNotIn("'standard_price':",text)
        self.assertNotIn('stock.quant',text)
        self.assertNotIn('stock.move',text)

if __name__=='__main__':unittest.main()
