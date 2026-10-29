"""Actual method regression with minimal records; not a database/stock test."""
import ast
from pathlib import Path
from types import SimpleNamespace as N
import unittest

p=Path(__file__).resolve().parents[1]/'models/production_sizes.py'
tree=ast.parse(p.read_text())
c=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='Production')
node=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='_esi_primary_output_qty')
node.decorator_list=[]
ns={'UserError':ValueError,'_':lambda x:x}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(p),'exec'),ns)
primary=ns['_esi_primary_output_qty']
class Unit:
 def __init__(self, factor=1):self.factor=factor
 def _compute_quantity(self,qty,target,round=False):return qty*self.factor/target.factor
class Record(N):
 def ensure_one(self):pass
class TestTotal(unittest.TestCase):
 def order(self,total=50,mode=True):
  unit=Unit();product=object()
  return Record(product_qty=total,esi_size_batch=True,esi_native_total_mode=mode,product_id=product,uom_id=unit,
   bom_id=N(product_id=product,product_qty=50,uom_id=unit,byproduct_ids=[N(uom_id=unit,product_qty=20)]))
 def test_50_is_split_as_30_and_20(self):self.assertEqual(primary(self.order()),30)
 def test_scaled_total(self):self.assertEqual(primary(self.order(100)),60)
 def test_legacy_unchanged(self):self.assertEqual(primary(self.order(30,False)),30)
 def test_invalid_total_rejected(self):
  mo=self.order();mo.bom_id.byproduct_ids[0].product_qty=55
  with self.assertRaises(ValueError):primary(mo)
 def test_units(self):
  mo=self.order();mo.bom_id.uom_id=Unit(10);mo.bom_id.product_qty=5
  self.assertEqual(primary(mo),30)
if __name__=='__main__':unittest.main()
