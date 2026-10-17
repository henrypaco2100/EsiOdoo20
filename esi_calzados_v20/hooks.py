def mark_existing_components(env):
    # Only existing materials are opted in, including archived recipes/history.
    # Executed once on installation/upgrade, never on ordinary product searches.
    materials = env['mrp.bom.line'].with_context(active_test=False).search([]).product_id
    materials |= env['stock.move'].with_context(active_test=False).search([
        ('raw_material_production_id', '!=', False)]).product_id
    materials.product_tmpl_id.with_context(active_test=False).filtered(
        lambda p: not p.esi_component_ok).write({'esi_component_ok': True})


def post_init_hook(env):
    mark_existing_components(env)
