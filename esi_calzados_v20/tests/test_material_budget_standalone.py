"""Execute production shortage method with ORM doubles; no database test."""
import ast
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace as N
import unittest

source = Path(__file__).resolve().parents[1] / 'models/material_budget.py'
tree = ast.parse(source.read_text())
cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'Production')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_esi_purchase_shortages')
node.decorator_list = []
ns = {'defaultdict': defaultdict, 'UserError': ValueError, '_': lambda s: s}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), ns)
shortages = ns['_esi_purchase_shortages']

class Uom:
    def __init__(self, factor=1): self.factor = factor
    def _compute_quantity(self, qty, target, round=False): return qty * self.factor / target.factor

class Product:
    id = 1
    is_storable = True
    uom_id = Uom()
    def __init__(self, free): self.free_qty = free
    def with_company(self, company): self.company = company; return self
    def with_context(self, **ctx): self.context = ctx; return self

class Moves(list):
    def filtered(self, predicate): return Moves(m for m in self if predicate(m))
    @property
    def product_id(self): return list({m.product_id.id: m.product_id for m in self}.values())
    @property
    def ids(self): return list(range(1, len(self)+1))

class Env:
    def __init__(self, company, lines): self.companies = [company]; self.lines = lines
    def __getitem__(self, key): return self
    def search(self, domain): self.domain = domain; return self.lines

class Order:
    id = 7
    state = 'confirmed'
    def ensure_one(self): pass
    def check_access(self, action): pass
    def __init__(self, quantities, free=0, purchase=0, received=0):
        self.company_id = N(id=3)
        self.location_src_id = N(id=8)
        p = self.product = Product(free)
        self.move_raw_ids = Moves(N(product_id=p, product_uom_qty=q, quantity=r, uom_id=Uom(factor),
            location_id=self.location_src_id, state='assigned') for q,r,factor in quantities)
        self.env = Env(self.company_id, [N(product_id=p, product_qty=purchase, qty_received=received, uom_id=Uom())])

class TestMaterialNeed(unittest.TestCase):
    def test_duplicate_components_share_free_stock_once(self):
        mo = Order([(10,2,1), (10,3,1)], free=4, purchase=6)
        row, = shortages(mo)
        self.assertEqual(row['shortage'], 5)
        self.assertEqual(mo.product.context['location'], 8)
        self.assertEqual(mo.product.company.id, 3)
    def test_units_are_converted(self):
        mo = Order([(2,1,12)], free=2, purchase=3)
        self.assertEqual(shortages(mo)[0]['shortage'], 7)
    def test_received_purchase_not_deducted_twice(self):
        mo = Order([(20,0,1)], free=5, purchase=10, received=5)
        self.assertEqual(shortages(mo)[0]['shortage'], 10)
    def test_covered_and_negative_free(self):
        self.assertEqual(shortages(Order([(5,0,1)], free=9))[0]['shortage'], 0)
        self.assertEqual(shortages(Order([(5,0,1)], free=-9))[0]['shortage'], 5)
    def test_done_and_company_guard(self):
        mo = Order([(5,0,1)])
        mo.state = 'done'
        self.assertEqual(shortages(mo), [])
        mo.env.companies = []
        with self.assertRaises(ValueError): shortages(mo)
    def test_mixed_locations_rejected(self):
        mo = Order([(5,0,1)])
        mo.move_raw_ids[0].location_id = N(id=99)
        with self.assertRaises(ValueError): shortages(mo)

if __name__ == '__main__': unittest.main()
