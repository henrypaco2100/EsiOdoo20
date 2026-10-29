import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class TranslationRegression(unittest.TestCase):
    def test_real_prepare_method_keeps_translation_callable(self):
        source = Path(__file__).parents[1] / 'models/production_plan.py'
        tree = ast.parse(source.read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_esi_prepare_plan_values')
        namespace = {'_': lambda text: text, 'UserError': RuntimeError}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(source), 'exec'), namespace)
        class CompanyModel:
            def browse(self, company_id):
                return self
            def exists(self):
                return False
        class Environment:
            company = SimpleNamespace(id=1)
            def __getitem__(self, name):
                return CompanyModel()
        # Execute the actual method, not a rewritten version. Previously the
        # local '_' unpacking raised UnboundLocalError instead of this message.
        with self.assertRaisesRegex(RuntimeError, 'Active la compañía'):
            namespace['_esi_prepare_plan_values'](SimpleNamespace(env=Environment()), {})

    def test_no_translation_function_shadowed_in_models(self):
        for path in (Path(__file__).parents[1] / 'models').glob('*.py'):
            for function in ast.walk(ast.parse(path.read_text())):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                calls_translation = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_' for n in ast.walk(function))
                shadows_translation = any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == '_' for n in ast.walk(function))
                self.assertFalse(calls_translation and shadows_translation, (path.name, function.name))
