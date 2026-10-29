import importlib.util
from pathlib import Path
import unittest
path=Path(__file__).parents[1]/'models/batch_math.py'
s=importlib.util.spec_from_file_location('math_under_test',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_sizes(self):self.assertEqual(m.cost_shares([30,20,10]),[50,33.33,16.67])
 def test_rounding(self):self.assertEqual(m.cost_shares([1,1,1]),[33.34,33.33,33.33])
 def test_total(self):self.assertEqual(round(sum(m.cost_shares([5,7,9,11,13])),2),100)
 def test_bad_values(self):
  for values in [[],[0,1],[-1,2],[float('nan'),2],[float('inf'),1],[1e-12,100]]:
   with self.assertRaises(ValueError):m.cost_shares(values)
if __name__=='__main__':unittest.main()
