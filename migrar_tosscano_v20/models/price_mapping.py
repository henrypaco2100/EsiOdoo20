"""Map model-level source prices to imported templates without fuzzy aliases."""
import math


def resolve_prices(finished, source):
    by_code = {}
    for row in source['rows']:
        code = row['code']
        if code in by_code:
            raise ValueError('Código de tarifa duplicado: ' + code)
        for key in ('retail', 'wholesale'):
            value = row[key]
            if key == 'wholesale' and value is None:
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Precio no válido: %s / %s' % (code, key))
        by_code[code] = row
    plan, missing, used = [], [], set()
    for product in finished:
        candidates = [code for code in by_code if product['code'] == code or product['code'].startswith(code + '-')]
        if not candidates:
            missing.append(product['code'])
            continue
        code = max(candidates, key=len)
        row = by_code[code]
        used.add(code)
        plan.append({'key': product['key'], 'code': product['code'], 'source_code': code,
                     'retail': row['retail'], 'wholesale': row['wholesale'] if row['wholesale'] is not None else row['retail'],
                     'wholesale_fallback': row['wholesale'] is None, 'source_row': row['row']})
    return plan, missing, sorted(set(by_code) - used)
