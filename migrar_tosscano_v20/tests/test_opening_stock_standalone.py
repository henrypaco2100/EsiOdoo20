"""Execute the real importer method against in-memory ORM doubles."""
import ast
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

source=ast.parse((Path(__file__).parents[1]/'models/direct.py').read_text())
cls=next(n for n in source.body if isinstance(n,ast.ClassDef))
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='action_import_stock')
namespace={'defaultdict':defaultdict,'UserError':RuntimeError,'_':lambda text,*args:text % args if args else text}
exec(compile(ast.Module(body=[method],type_ignores=[]),'stock_importer','exec'),namespace)
run=namespace['action_import_stock']

class StockImportTests(TestCase):
    def setup_import(self,key='pt:shoe:40',cost=0,branches=('FABRICA CALZADO',)):
        migration=SimpleNamespace(**{name:MagicMock() for name in ['_lock','_configure_category_accounting','_ref','_bind','_uom','_source','write']})
        migration.data_imported=True
        migration.import_log=''
        migration.valuation_pending_log=''
        refs={}
        unit=object()
        product=MagicMock(id=100,display_name='Calzado talla 40',standard_price=cost,uom_id=unit)
        product.with_company.return_value=product
        refs[key]=product
        migration._ref.side_effect=lambda k:refs.get(k)
        migration._bind.side_effect=lambda k,p:refs.update({k:p})
        migration._uom.return_value=unit
        migration._source.return_value={'stock':[{'product':key,'branch':b,'qty':30,'cost':None,'uom':'PAR'} for b in branches]}
        for i,field in enumerate(['warehouse_factory_id','warehouse_cbba_id','warehouse_scz_id'],1):
            setattr(migration,field,SimpleNamespace(company_id=SimpleNamespace(id=i),lot_stock_id=SimpleNamespace(id=10+i)))
        moves=MagicMock();moves.search_count.return_value=0
        quant_model=MagicMock();quant_model.with_company.return_value=quant_model
        quant_model.with_context.return_value=quant_model;quant_model.search.return_value=[]
        quant=MagicMock();quant.with_context.return_value=quant;quant.action_apply_inventory.return_value=None
        quant_model.create.return_value=quant
        migration.env={'stock.move':moves,'stock.quant':quant_model}
        def write(vals):
            for k,v in vals.items():setattr(migration,k,v)
        migration.write.side_effect=write
        return migration,quant_model,quant,moves,refs

    def test_finished_without_cost_is_loaded_and_flagged(self):
        m,q,quant,moves,refs=self.setup_import()
        run(m)
        q.create.assert_called_once_with({'product_id':100,'location_id':11,'inventory_quantity':30.0})
        quant.action_apply_inventory.assert_called_once_with()
        self.assertIn('costo cero',m.valuation_pending_log)
        self.assertTrue(m.stock_imported)

    def test_rerun_does_not_double_opening(self):
        m,q,quant,moves,refs=self.setup_import()
        run(m);run(m)
        self.assertEqual(q.create.call_count,1)
        self.assertEqual(quant.action_apply_inventory.call_count,1)
        self.assertEqual(m.valuation_pending_log.count('costo cero'),1)

    def test_each_branch_uses_own_warehouse(self):
        m,q,quant,moves,refs=self.setup_import(branches=('FABRICA CALZADO','CBBA','SCZ'))
        run(m)
        self.assertEqual([call.args[0]['location_id'] for call in q.create.call_args_list],[11,12,13])
        self.assertEqual(len([k for k in refs if k.startswith('balance:')]),3)

    def test_existing_finished_cost_preserved(self):
        m,q,quant,moves,refs=self.setup_import(cost=75)
        run(m)
        self.assertEqual(refs['pt:shoe:40'].standard_price,75)
        self.assertEqual(m.valuation_pending_log,'')
        self.assertEqual(q.create.call_count,1)

    def test_material_without_cost_still_blocked(self):
        m,q,quant,moves,refs=self.setup_import(key='mp:22')
        run(m)
        q.create.assert_not_called()
        self.assertFalse(m.stock_imported)

    def test_existing_moves_not_overwritten(self):
        m,q,quant,moves,refs=self.setup_import()
        moves.search_count.return_value=1
        run(m)
        q.create.assert_not_called()
        self.assertFalse(m.stock_imported)

    def test_negative_cost_not_loaded(self):
        m,q,quant,moves,refs=self.setup_import(cost=-1)
        run(m)
        q.create.assert_not_called()

    def test_aggregate_source_rows_for_same_variant(self):
        m,q,quant,moves,refs=self.setup_import()
        row=dict(m._source.return_value['stock'][0],qty=20)
        m._source.return_value['stock'].append(row)
        run(m)
        self.assertEqual(q.create.call_args.args[0]['inventory_quantity'],50)
