"""Pure arithmetic for a physical ledger. No ORM access or inventory writes."""
from collections import defaultdict


def build_ledger(events, start, end):
    """Events sorted by (date, line id); keys identify warehouse/product scope.

    Internal transfers within a scope have incoming == outgoing and are skipped.
    No rounding until presentation. No totals across products with different units.
    """
    groups = defaultdict(lambda: {'opening': 0.0, 'incoming': 0.0,
                                  'outgoing': 0.0, 'closing': 0.0, 'lines': []})
    for event in sorted(events, key=lambda e: (e['date'], e['id'])):
        if event['date'] >= end or event['incoming'] == event['outgoing']:
            continue
        group = groups[event['key']]
        delta = event['incoming'] - event['outgoing']
        if event['date'] < start:
            group['opening'] += delta
            group['closing'] += delta
        else:
            group['incoming'] += event['incoming']
            group['outgoing'] += event['outgoing']
            group['closing'] += delta
            group['lines'].append(dict(event, balance=group['closing']))
    return dict(groups)
