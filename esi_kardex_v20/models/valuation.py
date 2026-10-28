"""Read-only arithmetic; values are supplied by native Odoo valuation."""
def movement_unit_value(value, signed_quantity, fallback):
    # A zero-valued native movement is really zero: do not replace it with
    # today's cost. Only internal/unvalued movements use the dated fallback.
    return value / signed_quantity if signed_quantity else fallback()

def reconcile_values(events, initial, closing, currency):
    running, incoming, outgoing = initial, 0.0, 0.0
    for event in events:
        vin = event['incoming'] * event['unit_value']
        vout = event['outgoing'] * event['unit_value']
        incoming += vin
        outgoing += vout
        running += vin - vout
        event['money'] = [currency,event['unit_value'],0.0,vin,vout,0.0,running]
    return initial, incoming, outgoing, closing-running, closing
