from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Sale(models.Model):
    _inherit = 'sale.order'
    esi_branch_ref = fields.Char(string='Referencia de sucursal', readonly=True, copy=False, tracking=True)
    def _get_invoice_grouping_keys(self):
        return super()._get_invoice_grouping_keys() + ['esi_store_id']
    def action_confirm(self):
        for order in self:
            order._esi_apply_store_analytic(only_empty=True)
            if order.esi_store_id and not order.esi_branch_ref:
                order.esi_branch_ref = '%s-%s' % (order.esi_store_id.code, order.name)
        return super().action_confirm()
    def write(self, vals):
        if 'esi_store_id' in vals and any(o.state in ('sale','cancel') and o.esi_store_id.id != vals['esi_store_id'] for o in self):
            raise UserError(_('La sucursal de una venta confirmada no se puede cambiar.'))
        return super().write(vals)

class Purchase(models.Model):
    _inherit = 'purchase.order'
    @api.model_create_multi
    def create(self, vals_list):
        # Automated replenishment follows its receiving warehouse, not the scheduler user.
        for vals in vals_list:
            if not vals.get('esi_store_id') and vals.get('picking_type_id'):
                op = self.env['stock.picking.type'].browse(vals['picking_type_id'])
                vals['esi_store_id'] = op.warehouse_id.esi_store_id.id
        return super().create(vals_list)
    def button_confirm(self):
        self._esi_apply_store_analytic(only_empty=True)
        return super().button_confirm()

class SaleLine(models.Model):
    _inherit = 'sale.order.line'
    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        vals['esi_store_id'] = self.order_id.esi_store_id.id
        return vals

class PurchaseLine(models.Model):
    _inherit = 'purchase.order.line'
    def _prepare_account_move_line(self, move=False):
        vals = super()._prepare_account_move_line(move=move)
        vals['esi_store_id'] = self.order_id.esi_store_id.id
        return vals

class MoveLine(models.Model):
    _inherit = 'account.move.line'
    esi_store_id = fields.Many2one('esi.store', string='Sucursal comercial', check_company=True, index=True)

class Move(models.Model):
    _inherit = 'account.move'
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for move in records.filtered(lambda m: m.is_invoice(include_receipts=True)):
            stores = move.invoice_line_ids.esi_store_id
            # Consolidated vendor bills keep branch attribution on each line.
            if stores:
                move.esi_store_id = stores.id if len(stores) == 1 else False
        return records
    def action_esi_apply_store_analytic(self):
        if any(m.state != 'draft' for m in self):
            raise UserError(_('Solo puede aplicar la analítica en borradores.'))
        return super().action_esi_apply_store_analytic()

class Picking(models.Model):
    _inherit = 'stock.picking'
    esi_origin_store_id = fields.Many2one(related='location_id.warehouse_id.esi_store_id', string='Sucursal origen', store=True)
    esi_destination_store_id = fields.Many2one(related='location_dest_id.warehouse_id.esi_store_id', string='Sucursal destino', store=True)

class Orderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'
    esi_store_id = fields.Many2one(related='warehouse_id.esi_store_id', string='Sucursal abastecida', store=True)

class Payment(models.Model):
    _inherit = 'account.payment'
    esi_store_ids = fields.Many2many('esi.store', compute='_compute_esi_stores', string='Sucursales de las facturas')

    @api.depends('invoice_ids.esi_store_id', 'invoice_ids.invoice_line_ids.esi_store_id')
    def _compute_esi_stores(self):
        for payment in self:
            payment.esi_store_ids = payment.invoice_ids.esi_store_id | payment.invoice_ids.invoice_line_ids.esi_store_id
