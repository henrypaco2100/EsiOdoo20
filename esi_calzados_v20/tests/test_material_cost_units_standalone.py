import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase


def method(name):
    tree = ast.parse((Path(__file__).parents[1] / 'models/material_budget.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.decorator_list = []
    namespace = {'_': lambda text, *args: text % args}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<material_budget>', 'exec'), namespace)
    return namespace[name]


class TestMaterialUnits(TestCase):
    def test_incompatible_roll_and_metre_does_not_price(self):
        unit = NS(name='ROLLO', _has_common_reference=lambda other: False)
        product = NS(uom_id=unit, standard_price=45)
        product.with_company = lambda company: product
        move = NS(state='confirmed', product_id=product, uom_id=NS(name='m'),
                  company_id=NS(), product_uom_qty=4.5)
        method('_compute_esi_material_cost')([move])
        self.assertEqual(move.esi_estimated_cost, 0)
        self.assertIn('ROLLO', move.esi_cost_uom_issue)

    def test_compatible_cost_is_rounded_and_cancel_has_no_cost(self):
        unit = NS(_has_common_reference=lambda other: True, _compute_price=lambda price, other: price)
        product = NS(uom_id=unit, standard_price=14)
        product.with_company = lambda company: product
        move = NS(state='confirmed', product_id=product, uom_id=unit,
                  company_id=NS(currency_id=NS(round=lambda x: round(x, 2))), product_uom_qty=60)
        compute = method('_compute_esi_material_cost')
        compute([move])
        self.assertEqual(move.esi_estimated_cost, 840)
        move.state = 'cancel'
        compute([move])
        self.assertEqual(move.esi_estimated_cost, 0)

    def test_reserved_is_not_consumed(self):
        move = NS(state='confirmed', picked=False, quantity=4, product_uom_qty=5)
        compute = method('_compute_esi_remaining_to_consume')
        compute([move])
        self.assertEqual(move.esi_remaining_to_consume, 5)
        move.picked = True
        compute([move])
        self.assertEqual(move.esi_remaining_to_consume, 1)
