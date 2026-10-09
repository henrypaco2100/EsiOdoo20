"""Read-only inventory: exec(open('/ruta/auditar_sucursales.py').read()) in odoo shell.
Run with an authorized administrator on a restored copy. Does not use sudo or write.
"""
import json


def audit_branches(env):
    models = ('sale.order', 'purchase.order', 'account.move', 'account.move.line',
              'account.journal', 'stock.warehouse', 'stock.picking', 'stock.move',
              'stock.quant', 'stock.warehouse.orderpoint', 'mrp.production')
    result = {'companies': [], 'legacy_stores': [], 'counts': []}
    companies = env['res.company'].search([])
    for company in companies:
        result['companies'].append({'id': company.id, 'name': company.name, 'parent_id': company.parent_id.id or None})
        for name in models:
            if name not in env:
                continue
            model = env[name].with_context(allowed_company_ids=company.ids)
            domain = [('company_id', '=', company.id)]
            row = {'model': name, 'company_id': company.id, 'count': model.search_count(domain)}
            if 'esi_store_id' in model._fields:
                row['without_old_store'] = model.search_count(domain + [('esi_store_id', '=', False)])
            result['counts'].append(row)
    if 'esi.store' in env:
        for store in env['esi.store'].with_context(active_test=False).search([]):
            result['legacy_stores'].append({'id': store.id, 'name': store.display_name, 'company_id': store.company_id.id})
            for name in models:
                if name in env and 'esi_store_id' in env[name]._fields:
                    model = env[name].with_context(allowed_company_ids=store.company_id.ids)
                    result['counts'].append({'model': name, 'old_store_id': store.id,
                        'company_id': store.company_id.id,
                        'count': model.search_count([('company_id', '=', store.company_id.id), ('esi_store_id', '=', store.id)])})
    return result


print(json.dumps(audit_branches(env), ensure_ascii=False, indent=2))
