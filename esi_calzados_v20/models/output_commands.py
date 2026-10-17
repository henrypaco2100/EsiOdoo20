"""Resolve an editable output list without allowing foreign-line reassignment."""
import math


def resolve_outputs(existing, commands):
    rows = {key: dict(value) for key, value in existing.items()}
    counter = 0
    for command in commands:
        if not isinstance(command, (list, tuple)) or len(command) < 1:
            raise ValueError('Comando de línea inválido.')
        op = command[0]
        if op == 0 and len(command) == 3 and isinstance(command[2], dict):
            counter += 1
            rows[('new', counter)] = dict(command[2])
        elif op in (1, 2, 3) and len(command) >= 2:
            key = command[1]
            if not isinstance(key, int) or key not in rows:
                raise ValueError('La línea no pertenece a esta orden.')
            if op == 1 and len(command) == 3 and isinstance(command[2], dict):
                rows[key].update(command[2])
            elif op in (2, 3):
                del rows[key]
            else:
                raise ValueError('Actualización de línea inválida.')
        elif op == 5:
            rows.clear()
        else:
            raise ValueError('No se permite vincular líneas de otra orden.')
    result, seen = [], set()
    for row in rows.values():
        if 'production_id' in row:
            raise ValueError('No se permite reasignar líneas.')
        product = row.get('product_id')
        qty = float(row.get('quantity', 0))
        if not isinstance(product, int) or isinstance(product, bool) or product <= 0 or product in seen:
            raise ValueError('Seleccione una variante distinta en cada línea.')
        if not math.isfinite(qty) or qty <= 0:
            raise ValueError('Las cantidades deben ser positivas.')
        seen.add(product)
        result.append((product, qty))
    if not result:
        raise ValueError('Añada al menos una talla con cantidad positiva.')
    return result
