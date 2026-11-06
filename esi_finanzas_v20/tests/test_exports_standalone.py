import ast
from pathlib import Path
from types import SimpleNamespace
import io
from html import escape
import unittest
import xlsxwriter
import openpyxl
P=Path(__file__).parents[1]
T=ast.parse((P/'models/advanced_report.py').read_text())
FUNCTIONS=[n for n in ast.walk(T) if isinstance(n,ast.FunctionDef) and n.name in ('action_xlsx','_classic_html')]
S={'io':io,'xlsxwriter':xlsxwriter,'BinaryBytes':lambda x:x,'escape':escape};exec(compile(ast.Module(body=FUNCTIONS,type_ignores=[]),'<exports>','exec'),S)
def payload():
 return dict(title='BALANCE GENERAL',company=SimpleNamespace(name='Matriz <X>',vat='123'),scope='Matriz, Sucursal',notes='Tasa a fecha final.',comparison='2025-01-01 / 2025-12-31',journals='Todos',partial=True,currency=SimpleNamespace(name='USD'),posted=True,
 columns=[('code','CUENTA'),('name','TÍTULO'),('debit','DÉBITO'),('credit','CRÉDITO'),('amount','MONTO'),('compare','Anterior'),('difference','VARIACIÓN')],
 rows=[dict(key='test',code='001',name='=Título <prueba>',depth=2,group=True,style='heading',debit=700.,credit=0.,amount=100.,compare=90.,difference=10.)],fmt=lambda x:format(x,',.2f'))
class ExportTests(unittest.TestCase):
 def test_xlsx_numbers_codes_and_formula_safety(self):
  result={};obj=SimpleNamespace(kind='balance',date_from='2026-01-01',date_to='2026-12-31',_name='esi.finance.report',id=1,_classic_payload=payload)
  def write(values):
   result.update(values)
   for key,value in values.items():setattr(obj,key,value)
  obj.write=write;S['action_xlsx'](obj)
  book=openpyxl.load_workbook(io.BytesIO(result['export_file']),data_only=False);sheet=book.active
  self.assertEqual(sheet['A9'].value,'001');self.assertEqual(sheet['A9'].data_type,'s')
  self.assertEqual(sheet['B9'].data_type,'s');self.assertEqual(sheet['E9'].value,100)
  self.assertEqual(sheet['E9'].number_format,'#,##0.00');self.assertEqual(sheet['F9'].value,90)
  self.assertEqual(sheet['G9'].value,10);self.assertEqual(sheet['D8'].value,'CRÉDITO')
 def test_preview_escaping_and_two_decimals(self):
  obj=SimpleNamespace(date_from='2026-01-01',date_to='2026-12-31');html=S['_classic_html'](obj,payload())
  self.assertIn('Matriz &lt;X&gt;',html);self.assertIn('100.00',html);self.assertIn('DÉBITO',html)
  self.assertIn('Comparación',html);self.assertNotIn('<prueba>',html)
