import ast
from pathlib import Path
from types import SimpleNamespace as N
import unittest

ROOT = Path(__file__).parents[1]

class Rows(list):
    def filtered(self, fn): return Rows(x for x in self if fn(x))


def load(name, method):
    tree=ast.parse((ROOT/'models'/name).read_text())
    node=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body
              if isinstance(n,ast.FunctionDef) and n.name==method)
    node.decorator_list=[]
    env={'UserError':ValueError,'_':lambda text,**kw:text%kw if kw else text}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),name,'exec'),env)
    return env[method]

class CompletionTests(unittest.TestCase):
    def order(self):
        unit=N(compare=lambda a,b:(a>b)-(a<b))
        template=object()
        outputs=Rows(N(state='confirmed',product_id=N(product_tmpl_id=template),
                       quantity=q*40/60, product_uom_qty=q) for q in (10,40,10))
        raw=Rows(N(state='confirmed',picked=False,quantity=40,product_uom_qty=60,
                   uom_id=unit,product_id=N(display_name='Material')) for i in range(3))
        return N(esi_size_batch=True,esi_native_total_mode=True,state='progress',
                 product_qty=60,qty_producing=40,product_id=N(product_tmpl_id=template),
                 move_finished_ids=outputs,move_raw_ids=raw)

    def prepare(self,mo):
        load('multisize_completion.py','_esi_prepare_full_size_completion')(Rows([mo]))

    def test_exact_sizes_and_full_materials(self):
        mo=self.order();self.prepare(mo)
        self.assertEqual([m.quantity for m in mo.move_finished_ids],[10,40,10])
        self.assertEqual([m.quantity for m in mo.move_raw_ids],[60,60,60])
        self.assertEqual(mo.qty_producing,60)
        self.prepare(mo)
        self.assertEqual(sum(m.quantity for m in mo.move_finished_ids),60)

    def test_explicit_partial_consumption_requires_review(self):
        mo=self.order();mo.move_raw_ids[0].picked=True
        with self.assertRaisesRegex(ValueError,'40 registrados'):
            self.prepare(mo)

    def test_additional_actual_consumption_preserved(self):
        mo=self.order();mo.move_raw_ids[0].picked=True;mo.move_raw_ids[0].quantity=65
        self.prepare(mo)
        self.assertEqual(mo.move_raw_ids[0].quantity,65)

    def test_posted_outputs_are_never_rewritten(self):
        mo=self.order();mo.move_finished_ids[0].state='done'
        before=mo.move_finished_ids[0].quantity
        with self.assertRaisesRegex(ValueError,'contabilizadas'):self.prepare(mo)
        self.assertEqual(mo.move_finished_ids[0].quantity,before)

    def test_standard_order_unchanged(self):
        mo=self.order();mo.esi_size_batch=False
        self.prepare(mo)
        self.assertEqual(mo.qty_producing,40)
        self.assertEqual(mo.move_raw_ids[0].quantity,40)

    def test_produced_total_excludes_unposted_picked_moves(self):
        source=(ROOT/'models/production_sizes.py').read_text()
        tree=ast.parse(source)
        node=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body
                  if isinstance(n,ast.FunctionDef) and n.name=='_get_produced_qty')
        body=ast.unparse(node)
        self.assertIn("m.state == 'done'",body)
        self.assertNotIn('m.picked',body)
