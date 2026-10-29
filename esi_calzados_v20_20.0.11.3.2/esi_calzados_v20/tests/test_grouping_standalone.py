import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('grouping', Path(__file__).parents[1] / 'models/grouping_math.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
key = module.production_key


class GroupingTests(unittest.TestCase):
    def test_user_example_50_black_30_red(self):
        rows = [(40, 'black', 20), (39, 'black', 20), (41, 'black', 10), (40, 'red', 30)]
        result = {}
        for i, (size, color, qty) in enumerate(rows):
            k = key(1, [(1, size), (2, color), (3, 'classic'), (4, 'leather')], [1], i)
            result[k] = result.get(k, 0) + qty
        self.assertEqual(sorted(result.values()), [30, 50])

    def test_all_other_attributes_separate(self):
        original = [(1, 40), (2, 100), (3, 200), (4, 300)]
        for index in (1, 2, 3):
            other = list(original)
            attr, value = other[index]
            other[index] = (attr, value + 1)
            self.assertNotEqual(key(1, original, [1], 1), key(1, other, [1], 2))

    def test_without_flag_separate_skus(self):
        self.assertNotEqual(key(1, [(1, 40)], [], 1), key(1, [(1, 41)], [], 2))

    def test_templates_separate(self):
        self.assertNotEqual(key(1, [(1, 40)], [1], 1), key(2, [(1, 40)], [1], 2))


if __name__ == '__main__':
    unittest.main()
