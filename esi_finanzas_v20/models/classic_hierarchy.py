"""Read-only hierarchy aggregation. No accounting records are changed."""
def build_hierarchy(accounts, direct, max_depth=0, show_zero=False, tolerance=.005, custom_order=None):
    custom_order = custom_order or {}
    def order_key(key):
        return (custom_order.get(key, 1000000), accounts[key]['code'], key)
    totals = {key: list(direct.get(key, (0., 0., 0.))) for key in accounts}
    parents = {}
    for key, value in accounts.items():
        parent = value.get('parent')
        if parent in accounts and parent != key:
            parents[key] = parent
    # Every posting contributes once to each ancestor, even where parents have postings.
    for key, values in direct.items():
        visited = {key}
        parent = parents.get(key)
        while parent and parent not in visited:
            visited.add(parent)
            totals[parent] = [a+b for a,b in zip(totals[parent], values)]
            parent = parents.get(parent)
    children = {}
    for key in accounts:
        children.setdefault(parents.get(key), []).append(key)
    rows, visited = [], set()
    def visit(key, depth):
        if key in visited:
            return
        visited.add(key)
        value = accounts[key]
        opening, debit, credit = totals[key]
        closing = opening + debit - credit
        typ = value['type']
        amount = -closing if typ.startswith(('liability','equity','income')) else closing
        if (not max_depth or depth <= max_depth) and (show_zero or any(abs(x)>=tolerance for x in (opening,debit,credit,closing))):
            rows.append(dict(key='account:'+str(key),code=value['code'], name=value['name'], depth=depth,
                group=bool(children.get(key)), opening=opening, debit=debit,
                credit=credit, closing=closing, amount=amount, summary=False))
        for child in sorted(children.get(key, []), key=order_key):
            visit(child, depth+1)
    for root in sorted(children.get(None, []), key=order_key):
        visit(root, 1)
    # Detect malformed cycles instead of silently omitting accounts.
    if len(visited) != len(accounts):
        raise ValueError('El plan de cuentas contiene una jerarquía circular.')
    return rows
