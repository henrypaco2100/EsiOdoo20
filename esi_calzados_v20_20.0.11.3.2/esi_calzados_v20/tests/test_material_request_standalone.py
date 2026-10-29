import ast
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).parents[1] / 'models'


class RequestError(Exception):
    pass


def function(filename, cls, name):
    tree = ast.parse((ROOT / filename).read_text())
    model = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in model.body if isinstance(n, ast.FunctionDef) and n.name == name)


class Lines(list):
    def filtered(self, condition):
        return Lines(r for r in self if (getattr(r, condition) if isinstance(condition, str) else condition(r)))


class Supplier:
    def __init__(self, identifier, company=None):
        self.id = identifier
        self.company_id = company

    def __bool__(self):
        return bool(self.id)

    def check_access(self, operation):
        pass


def group(suppliers):
    # Execute the actual wizard's grouping loop, with fixed shortage fixtures.
    method = function('material_budget.py', 'MaterialPurchase', 'action_create_rfq')
    loop = next(n for n in method.body if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'line')
    company = NS(id=1)
    lines = Lines()
    latest = {}
    for i, supplier in enumerate(suppliers, 1):
        product = NS(id=i, purchase_ok=True, display_name='Material %s' % i,
                     uom_id=NS(is_zero=lambda qty: qty == 0))
        lines.append(NS(selected=True, product_id=product, supplier_id=Supplier(supplier)))
        latest[i] = {'product': product, 'shortage': i * 10}
    scope = {'self': NS(line_ids=lines), 'mo': NS(company_id=company), 'latest': latest,
             'grouped': defaultdict(list), 'seen': set(), 'UserError': RequestError,
             '_': lambda text, *args: text % args if args else text}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])), 'wizard_grouping', 'exec'), scope)
    return {key: [r['product'].id for r in rows] for key, rows in scope['grouped'].items()}


def validate(vendor, material, state):
    node = function('purchase_material_request.py', 'PurchaseOrder', '_esi_check_request_vendor')
    node.decorator_list = []
    scope = {'ValidationError': RequestError, '_': lambda text: text}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), 'vendor_guard', 'exec'), scope)
    scope[node.name]([NS(partner_id=vendor, esi_material_request=material, state=state)])


class MaterialRequestTests(unittest.TestCase):
    def test_all_without_vendor_in_one_request(self):
        self.assertEqual(group([False, False, False]), {False: [1, 2, 3]})

    def test_mixed_vendor_and_unassigned(self):
        self.assertEqual(group([False, 7, 7, False, 9]), {False: [1, 4], 7: [2, 3], 9: [5]})

    def test_same_vendor_one_request(self):
        self.assertEqual(group([7, 7, 7]), {7: [1, 2, 3]})

    def test_different_vendors_separate(self):
        self.assertEqual(group([7, 8, 9]), {7: [1], 8: [2], 9: [3]})

    def test_unassigned_draft_and_cancel_are_valid(self):
        validate(False, True, 'draft')
        validate(False, True, 'cancel')

    def test_unassigned_cannot_progress_to_purchase(self):
        for state in ('sent', 'to approve', 'purchase', 'done'):
            with self.subTest(state=state), self.assertRaises(RequestError):
                validate(False, True, state)

    def test_normal_purchase_requires_vendor(self):
        with self.assertRaises(RequestError):
            validate(False, False, 'draft')

    def test_vendor_assigned_can_confirm(self):
        validate(7, True, 'purchase')
        validate(7, False, 'purchase')


if __name__ == '__main__':
    unittest.main()
