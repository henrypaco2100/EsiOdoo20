import importlib.util
from pathlib import Path
import unittest
from lxml import html
P=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('layout',P/'models/layout.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class LayoutTests(unittest.TestCase):
    headers=['Sucursal / compañía','Moneda','Código','Descripción','Unidad','PU','TOTAL']+[str(i) for i in range(27,47)]+['Valor']
    row=['CBBA','BOB','M-L-01-03-00-PILOTO','Calzado <seguro> & cuero','PAR',152.35,50]+[0]*19+[50]+[7617.5]
    def test_all_columns_and_values_preserved(self):
        doc=html.fromstring(m.render_matrix('Prueba',self.headers,[self.row]))
        self.assertEqual(len(doc.xpath('//col')),len(self.headers))
        self.assertEqual(len(doc.xpath('//td')),len(self.row))
        self.assertIn('Calzado <seguro> & cuero',doc.text_content())
        self.assertFalse(doc.xpath('//seguro'))
        self.assertIn('7,617.50',doc.text_content())
    def test_widths_and_scroll(self):
        self.assertGreater(m.column_width('Descripción'),7*m.column_width('40'))
        doc=html.fromstring(m.render_matrix('Prueba',self.headers,[self.row]))
        self.assertIn('overflow-x:auto',doc.xpath('//div[@class="esi-size-scroll"]')[0].get('style'))
        self.assertIn('table-layout:fixed',doc.xpath('//table')[0].get('style'))
    def test_pdf_has_no_horizontal_scroller(self):
        doc=html.fromstring(m.render_matrix('Prueba',self.headers,[self.row],True))
        self.assertNotIn('overflow',doc.xpath('//div[@class="esi-size-scroll"]')[0].get('style'))
        self.assertIn('width:100%',doc.xpath('//table')[0].get('style'))
        self.assertIn('table-header-group',doc.xpath('//thead')[0].get('style'))
