from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def size_key(value):
    try:
        return (0, Decimal(value.replace(',', '.')), value)
    except InvalidOperation:
        return (1, Decimal(0), value.casefold())

def normalize_cost(value, rounding=None):
    """Normalize a cost to the currency rounding used by the report.

    Odoo may store slightly different binary/AVCO values which are displayed as
    the same monetary amount (for example 195.629999 and 195.630001 -> 195.63).
    Those must not make the matrix report say 'Variable'.
    """
    if not rounding:
        return value
    try:
        step = Decimal(str(rounding))
        if step <= 0:
            return value
        amount = Decimal(str(value))
        units = (amount / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return float(units * step)
    except (InvalidOperation, TypeError, ValueError):
        return value

def build_matrix(entries, include_zero=False, cost_rounding=None):
    """Entries already scoped by warehouse, company and record rules.

    ``cost_rounding`` should normally be the company currency rounding. Costs
    are normalized before deciding whether a row has one PU or variable PUs.
    """
    sizes = sorted({e['size'] for e in entries}, key=size_key)
    groups = {}
    for e in entries:
        key = (e['template'], tuple(e['attributes']), e['unit'])
        row = groups.setdefault(key, {'code':e['code'], 'name':e['name'], 'unit':e['unit'],
                                     'cells':defaultdict(float), 'costs':set(), 'value':0.0})
        row['cells'][e['size']] += e['qty']
        cost = normalize_cost(e['cost'], cost_rounding)
        row['costs'].add(cost)
        row['value'] += e['qty'] * cost
    rows = []
    totals = defaultdict(lambda: defaultdict(float))
    for row in sorted(groups.values(), key=lambda r: (r['code'],r['name'])):
        cells = [row['cells'][s] for s in sizes]
        if not include_zero and not any(abs(q) > 1e-8 for q in cells):
            continue
        cost = next(iter(row['costs'])) if len(row['costs']) == 1 else 'Variable'
        rows.append([row['code'],row['name'],row['unit'],cost,sum(cells)] + cells + [row['value']])
        for s, q in zip(sizes,cells): totals[row['unit']][s] += q
        totals[row['unit']]['value'] += row['value']
    for unit, values in sorted(totals.items()):
        cells = [values[s] for s in sizes]
        rows.append(['','TOTAL',unit,'',sum(cells)] + cells + [values['value']])
    return ['Código','Descripción','Unidad','PU','TOTAL'] + sizes + ['Valor'], rows
