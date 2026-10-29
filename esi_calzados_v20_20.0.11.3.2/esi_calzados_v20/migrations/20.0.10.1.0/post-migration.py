from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Identify only snapshots referenced by an OF, never regular recipe operations.
    orders = env['mrp.production'].with_context(active_test=False).search([
        ('esi_size_batch', '=', True), ('esi_source_bom_id', '!=', False)])
    for mo in orders:
        bom = mo.bom_id
        if not bom or bom == mo.esi_source_bom_id or bom.active:
            continue
        bom.esi_batch_snapshot = True
        moves = mo.move_finished_ids.filtered(lambda m: m.state != 'cancel')
        total = sum(m.uom_id._compute_quantity(m.product_uom_qty, mo.uom_id, round=False) for m in moves)
        # Only tag existing total-based snapshots. Never rewrite quantities of
        # legacy confirmed orders (primary-based) or completed stock moves.
        if moves and mo.uom_id.compare(total, mo.product_qty) == 0:
            bom.esi_total_basis = True
