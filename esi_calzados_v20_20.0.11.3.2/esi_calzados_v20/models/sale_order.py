from odoo import fields, models, Command, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    esi_production_group_ids = fields.One2many('esi.production.group', 'sale_id', string='Grupos de fabricación')

    def action_esi_production_group(self):
        self.ensure_one()
        self.check_access('read')
        self.env.cr.execute('SELECT id FROM sale_order WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['esi_production_group_ids'])
        groups = self.esi_production_group_ids.filtered(lambda g: g.state != 'cancel')
        if groups:
            return {'type': 'ir.actions.act_window', 'name': _('Grupos de fabricación'),
                'res_model': 'esi.production.group', 'view_mode': 'list,form', 'domain': [('id', 'in', groups.ids)]}
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Cree el grupo desde la cotización. Revise primero las órdenes automáticas de un pedido confirmado.'))
        lines = self.order_line.filtered(lambda l: not l.display_type and l.product_id.is_storable and l.product_uom_qty > 0)
        if not lines:
            raise UserError(_('La cotización no tiene productos almacenables con cantidad positiva.'))
        amounts = {}
        for line in lines:
            product = line.product_id
            amounts[product] = amounts.get(product, 0) + line.product_uom_id._compute_quantity(line.product_uom_qty, product.uom_id, round=False)
        group = self.env['esi.production.group'].with_company(self.company_id).create({
            'company_id': self.company_id.id, 'sale_id': self.id,
            'line_ids': [Command.create({'product_id': p.id, 'quantity': qty}) for p, qty in amounts.items()],
            'note': _('Revise las rutas MTO antes de confirmar la venta para evitar otra fabricación automática. Este grupo no sustituye las reglas de abastecimiento de la venta.')})
        return {'type': 'ir.actions.act_window', 'name': _('Grupo de fabricación'),
            'res_model': 'esi.production.group', 'view_mode': 'form', 'res_id': group.id}

    def _esi_check_manual_group_routes(self):
        for order in self:
            groups = order.esi_production_group_ids.filtered(lambda g: g.state != 'cancel')
            if not groups:
                continue
            products = groups.line_ids.product_id
            routes = products.route_ids | products.categ_id.total_route_ids | order.order_line.route_ids
            if routes.rule_ids.filtered(lambda r: r.procure_method in ('make_to_order', 'mts_else_mto')):
                raise UserError(_('Esta venta tiene un grupo de fabricación manual y rutas bajo pedido (MTO). Elija un solo flujo antes de confirmar: el grupo manual o el abastecimiento automático. No se han cambiado las rutas.'))

    def action_confirm(self):
        self._esi_check_manual_group_routes()
        return super().action_confirm()
