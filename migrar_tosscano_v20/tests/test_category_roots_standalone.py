import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

P = Path(__file__).parents[1]
tree = ast.parse((P/'models/direct.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_category')
ns = {'UserError': RuntimeError, '_': lambda s, *a: s % a}
exec(compile(ast.Module(body=[method], type_ignores=[]), 'category', 'exec'), ns)

class Category:
    def __init__(self, id, name, parent=False):
        self.id, self.name, self.parent = id, name, parent
        self.writes = []
    def __len__(self): return 1
    def write(self, vals):
        self.writes.append(vals)
        self.parent = vals['parent_id']

class Model:
    def __init__(self): self.rows = []
    def search(self, domain):
        name, parent = domain[0][2], domain[1][2]
        rows = [r for r in self.rows if r.name == name and r.parent == parent]
        return rows[0] if len(rows) == 1 else rows
    def create(self, vals):
        r = Category(len(self.rows)+1, vals['name'], vals['parent_id'])
        self.rows.append(r)
        return r

class CategoryRootTests(TestCase):
    def setup_data(self):
        model = Model()
        raw = model.create({'name':'Materia prima','parent_id':False})
        finished = model.create({'name':'Producto terminado','parent_id':False})
        roots = {'Materia prima':raw, 'Producto terminado':finished}
        m = SimpleNamespace(env={'product.category':model}, _category_root=roots.get)
        return m, model, roots

    def test_reparent_existing_family_keeps_leaf_identity_and_repeat(self):
        m, model, roots = self.setup_data()
        family = model.create({'name':'CUEROS','parent_id':False})
        leaf = model.create({'name':'NAPA','parent_id':family.id})
        for unused in range(2):
            self.assertIs(ns['_category'](m, 'Cueros', 'Napa'), leaf)
        self.assertEqual(family.parent, roots['Materia prima'].id)
        self.assertEqual(len(model.rows),4)
        self.assertEqual(len(family.writes),1)

    def test_new_finished_path_has_correct_root(self):
        m, model, roots = self.setup_data()
        leaf = ns['_category'](m, 'CALZADOS MILITAR', 'M-W-01', 'Producto terminado')
        family = next(r for r in model.rows if r.id == leaf.parent)
        self.assertEqual(family.parent,roots['Producto terminado'].id)

    def test_same_family_names_do_not_mix_types(self):
        m, model, roots = self.setup_data()
        a = ns['_category'](m, 'OTROS', 'A')
        b = ns['_category'](m, 'OTROS', 'A', 'Producto terminado')
        self.assertNotEqual(a.id,b.id)
        self.assertNotEqual(a.parent,b.parent)
