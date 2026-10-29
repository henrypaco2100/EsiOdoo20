import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('virtual_commands', Path(__file__).parents[1] / 'models/virtual_commands.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
clean = module.clean_virtual_commands


class TestVirtualCommands(unittest.TestCase):
    def test_unsaved_deletion(self):
        self.assertEqual(clean([(2, 'virtual_1162', 0)]), [])

    def test_create_then_delete(self):
        self.assertEqual(clean([(0, 'virtual_1', {'x': 1}), (3, 'virtual_1', 0)]), [])

    def test_create_then_update_without_mutating_input(self):
        commands = [(0, 'virtual_1', {'qty': 1}), (1, 'virtual_1', {'qty': 3})]
        self.assertEqual(clean(commands), [(0, 0, {'qty': 3})])
        self.assertEqual(commands[0][2], {'qty': 1})

    def test_real_commands_unchanged(self):
        commands = [(1, 12, {'qty': 3}), (2, 13, 0), (3, 14, 0), (4, 15, 0), (6, 0, [16])]
        self.assertEqual(clean(commands), commands)

    def test_standard_create_preserved(self):
        commands = [(0, 0, {'qty': 1}), (2, 'virtual_1162', 0)]
        self.assertEqual(clean(commands), commands[:1])

    def test_unknown_update_rejected(self):
        with self.assertRaises(ValueError):
            clean([(1, 'virtual_1', {'qty': 3})])

    def test_link_and_set_rejected(self):
        for commands in [[(4, 'virtual_1', 0)], [(6, 0, ['virtual_1'])]]:
            with self.assertRaises(ValueError):
                clean(commands)

    def test_duplicate_temporary_id_rejected(self):
        with self.assertRaises(ValueError):
            clean([(0, 'virtual_1', {}), (0, 'virtual_1', {})])


if __name__ == '__main__':
    unittest.main()
