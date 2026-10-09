"""Run with python3; tests arithmetic without pretending to run an Odoo server."""
import importlib.util
from pathlib import Path
import unittest
from datetime import datetime
spec = importlib.util.spec_from_file_location('kardex_balances', Path(__file__).resolve().parents[1] / 'models/balances.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
START, END = datetime(2026, 10, 1), datetime(2026, 11, 1)


def event(day, incoming=0, outgoing=0, key=(1, 10), ident=1):
    return dict(date=datetime.fromisoformat(day), incoming=incoming, outgoing=outgoing, key=key, id=ident)


class LedgerTests(unittest.TestCase):
    def test_opening_receipt_delivery_return_and_adjustment(self):
        data = [event('2026-09-30', 100), event('2026-10-01', 20),
                event('2026-10-02', outgoing=35), event('2026-10-03', 5),
                event('2026-10-04', outgoing=2)]
        result = module.build_ledger(data, START, END)[(1, 10)]
        self.assertEqual([result[k] for k in ['opening','incoming','outgoing','closing']], [100,25,37,88])
        self.assertEqual([r['balance'] for r in result['lines']], [120,85,90,88])

    def test_initial_and_end_boundaries(self):
        data = [event('2026-09-30T23:59:59', 7), event('2026-10-01', 3), event('2026-11-01', 999)]
        result = module.build_ledger(data, START, END)[(1,10)]
        self.assertEqual(result['opening'],7)
        self.assertEqual(result['closing'],10)
        self.assertEqual(len(result['lines']),1)

    def test_transfer_separate_warehouses(self):
        data = [event('2026-09-01',10), event('2026-10-02',outgoing=4), event('2026-10-02',4,key=(2,10))]
        result = module.build_ledger(data, START, END)
        self.assertEqual(result[(1,10)]['closing'],6)
        self.assertEqual(result[(2,10)]['closing'],4)
        self.assertEqual(sum(r['closing'] for r in result.values()),10)

    def test_internal_movement_not_double_counted(self):
        data = [event('2026-09-01',10), event('2026-10-02',4,4)]
        result = module.build_ledger(data, START, END)[(1,10)]
        self.assertEqual(result['closing'],10)
        self.assertEqual(result['incoming'],0)
        self.assertEqual(result['outgoing'],0)

    def test_products_not_summed_together(self):
        result = module.build_ledger([event('2026-10-02',2),event('2026-10-02',3,key=(1,11))],START,END)
        self.assertEqual(len(result),2)
        self.assertEqual(result[(1,10)]['closing'],2)
        self.assertEqual(result[(1,11)]['closing'],3)

    def test_stable_date_id_order(self):
        result = module.build_ledger([event('2026-10-02',outgoing=2,ident=2),event('2026-10-02',5,ident=1)],START,END)[(1,10)]
        self.assertEqual([r['balance'] for r in result['lines']],[5,3])

    def test_negative_stock_preserved(self):
        result = module.build_ledger([event('2026-10-02',outgoing=3)],START,END)[(1,10)]
        self.assertEqual(result['closing'],-3)

    def test_opening_only_product_kept(self):
        result = module.build_ledger([event('2026-09-01',7.125)],START,END)[(1,10)]
        self.assertEqual(result['closing'],7.125)
        self.assertEqual(result['lines'],[])

    def test_empty(self):
        self.assertEqual(module.build_ledger([],START,END),{})


if __name__ == '__main__':
    unittest.main()
