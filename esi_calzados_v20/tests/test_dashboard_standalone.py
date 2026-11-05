import ast
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

P = Path(__file__).parents[1]
tree = ast.parse((P/'models/center_dashboard.py').read_text())
fn = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='get_center_dashboard')
fn.decorator_list=[]
namespace = {'fields':NS(Date=NS(context_today=lambda obj:date(2026,11,5),
    to_date=date.fromisoformat)), 'timedelta':timedelta,
    'defaultdict':__import__('collections').defaultdict,
    'period_start':lambda d,group:d, 'UserError':RuntimeError, '_':lambda text:text}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'dashboard','exec'),namespace)

class Records(list):
    @property
    def ids(self):return [r.id for r in self]
    @property
    def id(self):return self[0].id if self else False
    @property
    def name(self):return self[0].name if self else False
    def __getitem__(self,index):
        result=super().__getitem__(index)
        return Records(result) if isinstance(index,slice) else result
    def __or__(self,other):return Records({x.id:x for x in list(self)+list(other)}.values())
    def check_access(self,operation):pass
    def exists(self):return self
    def filtered(self,name):return Records(x for x in self if getattr(x,name))
    def mapped(self,name):return [getattr(x,name) for x in self]

class DashboardTests(TestCase):
    def model(self):
        unit=NS(id=2,name='PAR')
        companies=Records([NS(id=1,name='Fábrica')])
        centers=[NS(id=11,name='Corte'),NS(id=12,name='Aparado')]
        stages=Records([NS(esi_center_step=1),NS(esi_center_step=2)])
        production=NS(id=50,workorder_ids=stages)
        events=Records([NS(quantity=80,uom_id=unit,workcenter_id=centers[0],
            advanced_at=datetime(2026,11,5,10),
            workorder_id=NS(production_id=production,esi_center_step=1)),
            NS(quantity=30,uom_id=unit,workcenter_id=centers[1],
            advanced_at=datetime(2026,11,5,11),
            workorder_id=NS(production_id=production,esi_center_step=2))])
        models={name:MagicMock() for name in ['uom.uom','esi.center.advance','mrp.workorder']}
        models['uom.uom'].browse.return_value=Records([unit])
        models['esi.center.advance']._read_group.return_value=[(unit,)]
        models['esi.center.advance'].search.return_value=events
        models['mrp.workorder'].search.return_value=Records([NS(workcenter_id=centers[0],_esi_center_amounts=lambda:(100,20))])
        env=MagicMock();env.companies=companies;env.company=companies[0]
        env.user.has_group.return_value=True;env.__getitem__.side_effect=models.__getitem__
        report=NS(_report_scope=lambda:([],ZoneInfo('America/La_Paz'),ZoneInfo('UTC')))
        obj=NS(env=env,create=lambda vals:report)
        return obj,models

    def test_kpis_do_not_call_all_advances_finished_pairs(self):
        obj,models=self.model()
        result=namespace['get_center_dashboard'](obj,{'date_from':'2026-11-05','date_to':'2026-11-05'})
        self.assertEqual(result['kpis'],{'advances':110,'finished':30,'orders':1,'pending':20})
        self.assertEqual(next(s for s in result['series'] if s['id']==11)['values'],[80])
        self.assertEqual(result['unit'],'PAR')
        self.assertIn(('uom_id','=',2),models['esi.center.advance'].search.call_args.args[0])

    def test_unauthorized_company_rejected(self):
        obj,models=self.model()
        with self.assertRaisesRegex(RuntimeError,'compañía activa'):
            namespace['get_center_dashboard'](obj,{'company_id':99})
        models['esi.center.advance'].search.assert_not_called()

    def test_negative_range_rejected(self):
        obj,models=self.model()
        with self.assertRaisesRegex(RuntimeError,'rango de fechas'):
            namespace['get_center_dashboard'](obj,{'date_from':'2026-11-06','date_to':'2026-11-05'})

    def test_frontend_uses_odoo_chart_lifecycle(self):
        source=(P/'static/src/dashboard/center_dashboard.js').read_text()
        self.assertIn('useChart',source)
        self.assertIn('standardActionServiceProps',source)
        self.assertNotIn('useState',source)
