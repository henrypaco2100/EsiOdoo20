"""Exercise route decisions without an Odoo server; ORM integration is separate."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


class RouteError(Exception):
    pass


def method(cls, name):
    source = Path(__file__).parents[1] / 'models/workcenter_route.py'
    tree = ast.parse(source.read_text())
    model = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in model.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    scope = {'UserError': RouteError, 'ValidationError': RouteError,
             '_': lambda text, **values: text % values if values else text}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), scope)
    return scope[name]


class Records(list):
    def filtered(self, condition):
        return Records(r for r in self if getattr(r, condition)) if isinstance(condition, str) else Records(filter(condition, self))

    def sorted(self, key):
        return Records(sorted(self, key=(lambda r: getattr(r, key)) if isinstance(key, str) else key))

    def __getitem__(self, key):
        value = super().__getitem__(key)
        return Records(value) if isinstance(key, slice) else value

    def __getattr__(self, name):
        return getattr(self[0], name) if self else False


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.production = NS(state='confirmed', product_qty=50, qty_producing=50,
                             uom_id=NS(compare=lambda a, b: (a > b) - (a < b)))
        self.production._esi_check_full_center_batch = lambda: method('Production', '_esi_check_full_center_batch')(Records([self.production]))
        self.stages = Records(NS(esi_center_step=i, state=state, workcenter_id=center,
                                production_id=self.production)
                             for i, state, center in [(1, 'ready', 'Corte'), (2, 'blocked', 'Aparado'), (3, 'blocked', 'Solado')])
        self.production.workorder_ids = self.stages

    def compute(self):
        records = Records([self.production])
        records.env = {'mrp.workorder': Records()}
        method('Production', '_compute_esi_current_center')(records)

    def test_first_center_then_next_keeps_history(self):
        self.compute()
        self.assertEqual(self.production.esi_current_center_id, 'Corte')
        self.stages[0].state = 'done'
        self.stages[1].state = 'ready'
        self.compute()
        self.assertEqual(self.production.esi_current_center_id, 'Aparado')
        self.assertEqual(self.production.esi_center_progress, '1 de 3 centros terminados')
        self.assertEqual(len(self.production.workorder_ids), 3)

    def test_all_finished_has_no_current_center(self):
        for stage in self.stages:
            stage.state = 'done'
        self.production.state = 'to_close'
        self.compute()
        self.assertFalse(self.production.esi_current_center_id)
        self.assertEqual(self.production.esi_center_progress, '3 de 3 centros terminados')

    def test_cancelled_order_has_no_current_center(self):
        self.production.state = 'cancel'
        self.compute()
        self.assertFalse(self.production.esi_current_center_id)

    def test_cannot_skip_previous_center(self):
        with self.assertRaises(RouteError):
            method('Workorder', '_esi_check_previous_centers')(Records([self.stages[1]]))

    def test_cancelled_previous_center_is_not_completed(self):
        self.stages[0].state = 'cancel'
        with self.assertRaises(RouteError):
            method('Workorder', '_esi_check_previous_centers')(Records([self.stages[1]]))

    def test_previous_done_allows_next(self):
        self.stages[0].state = 'done'
        method('Workorder', '_esi_check_previous_centers')(Records([self.stages[1]]))

    def test_partial_quantity_cannot_finish_stage(self):
        self.production.qty_producing = 30
        with self.assertRaises(RouteError):
            method('Workorder', '_esi_check_previous_centers')(Records([self.stages[0]]))

    def test_standard_workorders_are_unchanged(self):
        self.stages[0].esi_center_step = 0
        self.production.state = 'draft'
        method('Workorder', '_esi_check_previous_centers')(Records([self.stages[0]]))


if __name__ == '__main__':
    unittest.main()
