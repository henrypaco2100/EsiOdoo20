import importlib.util
from pathlib import Path
from unittest import TestCase

spec = importlib.util.spec_from_file_location('matrix',Path(__file__).parents[1]/'models/matrix.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MatrixTests(TestCase):
    def e(self,size='40',qty=10,cost=152,attributes=(1,),template=1,unit='PAR'):
        return dict(size=size,qty=qty,cost=cost,attributes=attributes,template=template,
                    unit=unit,name='Calzado',code='M-L-01')
    def test_sizes_numeric_and_totals(self):
        headers,rows=module.build_matrix([self.e('40',30),self.e('39',10),self.e('41',10)])
        self.assertEqual(headers[5:-1],['39','40','41'])
        self.assertEqual(rows[0][4:-1],[50,10,30,10])
        self.assertEqual(rows[0][-1],7600)
        self.assertEqual(rows[-1][4],50)
    def test_colors_separate(self):
        h,r=module.build_matrix([self.e(attributes=(1,)),self.e(attributes=(2,))])
        self.assertEqual(len(r),3)
    def test_templates_separate_even_same_names(self):
        h,r=module.build_matrix([self.e(template=1),self.e(template=2)])
        self.assertEqual(len(r),3)
    def test_zero_columns_and_zero_rows(self):
        h,r=module.build_matrix([self.e('40',10),self.e('46',0),self.e('35',0,template=2)])
        self.assertEqual(h[5:-1],['35','40','46'])
        self.assertEqual(len(r),2)
        self.assertEqual(len(module.build_matrix([self.e(qty=0)],True)[1]),2)
    def test_negatives_not_discarded(self):
        h,r=module.build_matrix([self.e('40',10),self.e('41',-10)])
        self.assertEqual(len(r),2)
        self.assertEqual(r[0][4],0)
    def test_variable_cost_not_misrepresented(self):
        h,r=module.build_matrix([self.e('40',10,100),self.e('41',20,150)])
        self.assertEqual(r[0][3],'Variable')
        self.assertEqual(r[0][-1],4000)
    def test_same_displayed_currency_cost_is_not_variable(self):
        h,r=module.build_matrix([
            self.e('40',10,195.629999),
            self.e('41',20,195.630001),
        ], cost_rounding=0.01)
        self.assertEqual(r[0][3],195.63)
        self.assertAlmostEqual(r[0][-1],5868.90, places=2)

    def test_different_displayed_currency_cost_is_variable(self):
        h,r=module.build_matrix([
            self.e('40',10,195.63),
            self.e('41',20,195.64),
        ], cost_rounding=0.01)
        self.assertEqual(r[0][3],'Variable')
    def test_totals_by_unit(self):
        h,r=module.build_matrix([self.e(),self.e(unit='UNIDAD')])
        self.assertEqual(len([v for v in r if v[1]=='TOTAL']),2)
    def test_empty_and_alpha_sizes(self):
        self.assertEqual(module.build_matrix([])[1],[])
        h,r=module.build_matrix([self.e('Sin talla'),self.e('XL'),self.e('9'),self.e('10')])
        self.assertEqual(h[5:7],['9','10'])
