"""Normalize temporary web row references before an ORM write; real IDs are untouched."""
from copy import deepcopy
import re


def clean_virtual_commands(commands):
    if not isinstance(commands, (list, tuple)):
        return commands
    result = []
    pending = {}
    for original in commands:
        command = deepcopy(original)
        if not isinstance(command, (list, tuple)) or len(command) < 2:
            result.append(command)
            continue
        op, row_id = command[:2]
        virtual = isinstance(row_id, str) and re.fullmatch(r'virtual_\d+', row_id)
        if op == 0 and virtual:
            if row_id in pending:
                raise ValueError('Identificador temporal repetido; recargue la receta.')
            pending[row_id] = len(result)
            result.append((0, 0, command[2]))
        elif virtual and op in (2, 3):
            if row_id in pending:
                result[pending.pop(row_id)] = None
            # An unsaved row has no persisted record to unlink.
        elif virtual and op == 1:
            if row_id not in pending:
                raise ValueError('Una línea temporal perdió sus datos; recargue la receta antes de guardar.')
            index = pending[row_id]
            result[index][2].update(command[2])
        elif virtual:
            raise ValueError('No se puede vincular una línea temporal; guarde o recargue la receta.')
        elif op == 6 and len(command) > 2 and any(isinstance(x, str) and x.startswith('virtual_') for x in command[2]):
            raise ValueError('La selección contiene líneas temporales; recargue la receta.')
        else:
            result.append(command)
        if op in (5, 6):
            pending.clear()
    return [cmd for cmd in result if cmd is not None]
