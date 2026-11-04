import ast
from datetime import date, timedelta
from pathlib import Path
from unittest import TestCase


class ReportPeriods(TestCase):
    def test_calendar_boundaries(self):
        tree = ast.parse((Path(__file__).parents[1] / 'models/center_report.py').read_text())
        fn = next(node for node in tree.body if getattr(node, 'name', '') == 'period_start')
        namespace = {'timedelta': timedelta}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<periods>', 'exec'), namespace)
        period = namespace['period_start']
        day = date(2026, 1, 1)
        self.assertEqual(period(day, 'day'), day)
        self.assertEqual(period(day, 'week'), date(2025, 12, 29))
        self.assertEqual(period(date(2026, 2, 27), 'month'), date(2026, 2, 1))
        self.assertEqual(period(date(2026, 12, 31), 'year'), day)
