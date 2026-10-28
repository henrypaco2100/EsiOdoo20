import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('valuation',Path(__file__).parents[1]/'models/valuation.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class ValuationTests(TestCase):
    def test_native_signed_outgoing(self):
        self.assertEqual(v.movement_unit_value(-1500,-10,lambda:99),150)
    def test_zero_native_value_is_not_current_cost(self):
        fallback=Mock(return_value=152)
        self.assertEqual(v.movement_unit_value(0,10,fallback),0)
        fallback.assert_not_called()
    def test_internal_transfer_fallback(self):
        self.assertEqual(v.movement_unit_value(0,0,lambda:148.33),148.33)
    def test_adjustment_without_quantity_movement(self):
        self.assertEqual(v.reconcile_values([],0,1520,'BOB'),(0,0,0,1520,1520))
    def test_mixed_movement_and_cost_revision(self):
        events=[dict(incoming=10,outgoing=0,unit_value=100),dict(incoming=0,outgoing=2,unit_value=100)]
        result=v.reconcile_values(events,0,960,'BOB')
        self.assertEqual(result,(0,1000,200,160,960))
        self.assertEqual(events[-1]['money'][-1],800)
    def test_negative_adjustment_and_opening(self):
        r=v.reconcile_values([],200,150,'BOB')
        self.assertEqual(r[3],-50)
        self.assertEqual(r[0]+r[1]-r[2]+r[3],r[4])
    def test_split_move_value_not_duplicated(self):
        price=v.movement_unit_value(500,10,lambda:0)
        events=[dict(incoming=3,outgoing=0,unit_value=price),dict(incoming=7,outgoing=0,unit_value=price)]
        self.assertEqual(v.reconcile_values(events,0,500,'BOB')[1],500)
