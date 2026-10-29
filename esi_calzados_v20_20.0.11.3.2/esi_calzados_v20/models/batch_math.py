"""Pure planned quantity allocation; never computes or writes inventory value."""
from decimal import Decimal, ROUND_FLOOR


def cost_shares(quantities):
    values = [Decimal(str(q)) for q in quantities]
    if not values or any(not q.is_finite() or q <= 0 for q in values):
        raise ValueError('Las cantidades deben ser positivas y finitas.')
    exact = [q / sum(values) * 10000 for q in values]
    units = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in exact]
    ranking = sorted(range(len(values)), key=lambda i: exact[i] - units[i], reverse=True)
    for i in ranking[:10000 - sum(units)]:
        units[i] += 1
    if any(u == 0 for u in units):
        raise ValueError('Una participación de costo sería cero. Divida el lote.')
    return [u / 100 for u in units]
