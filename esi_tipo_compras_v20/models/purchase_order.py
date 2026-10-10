from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    esi_purchase_type_id = fields.Many2one(
        'esi.purchase.type',
        check_company=True,
        string='Tipo de Compra',
        domain="[('company_id', '=', company_id)]",
        copy=True,
        help=(
            'Clasificación y opciones comerciales de la sucursal. '
            'No sustituye la operación de recepción, rutas ni reabastecimiento nativo de Odoo 20.'
        ),
    )

    esi_can_register_payment = fields.Boolean(compute='_compute_esi_can_register_payment')

    @api.constrains('company_id', 'esi_purchase_type_id')
    def _check_type_branch(self):
        for order in self:
            if order.esi_purchase_type_id and order.esi_purchase_type_id.company_id != order.company_id:
                raise ValidationError(_('El tipo pertenece a otra sucursal.'))

    @api.onchange('company_id')
    def _onchange_type_company(self):
        if self.esi_purchase_type_id.company_id != self.company_id:
            self.esi_purchase_type_id = False

    @api.depends('invoice_ids.state', 'invoice_ids.payment_state', 'esi_purchase_type_id.allow_payment')
    def _compute_esi_can_register_payment(self):
        for order in self:
            order.esi_can_register_payment = bool(
                order.esi_purchase_type_id.allow_payment
                and order.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted'
                    and inv.payment_state not in ('paid', 'reversed')
                    and inv.move_type == 'in_invoice'
                )
            )

    def action_esi_register_payment(self):
        self.ensure_one()
        self.check_access('read')
        if not self.esi_purchase_type_id.allow_payment:
            raise UserError(_('Este tipo no permite registrar pagos desde el pedido.'))
        invoices = self.invoice_ids.filtered(
            lambda inv: inv.state == 'posted'
            and inv.payment_state not in ('paid', 'reversed')
            and inv.move_type == 'in_invoice'
            and inv.company_id == self.company_id
        )
        if not invoices:
            raise UserError(_('No hay facturas publicadas pendientes de pago.'))
        invoices.check_access('read')
        return invoices.action_register_payment()

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.esi_purchase_type_id.journal_id:
            values['journal_id'] = self.esi_purchase_type_id.journal_id.id
        return values

    def action_esi_apply_type_flow(self):
        self.ensure_one()
        self.check_access('write')
        if self.state not in ('purchase', 'done'):
            raise UserError(_('Primero confirme el pedido.'))
        config = self.esi_purchase_type_id
        if not config:
            return False
        config.check_access('read')
        if config.company_id != self.company_id:
            raise UserError(_('El tipo pertenece a otra sucursal.'))
        if config.validation_picking:
            result = self._esi_validate_ready_pickings('incoming')
            if result:
                return result
        if config.create_invoice and self.invoice_status == 'to invoice':
            self.action_create_invoice()
        if config.validate_invoice:
            invoices = self.invoice_ids.filtered(
                lambda inv: inv.state == 'draft'
                and inv.move_type == 'in_invoice'
                and inv.company_id == self.company_id
            )
            invoices.check_access('write')
            invoices.action_post()
        return False

    def button_confirm(self):
        if len(self) > 1 and any(
            o.esi_purchase_type_id.validation_picking
            or o.esi_purchase_type_id.create_invoice
            or o.esi_purchase_type_id.validate_invoice
            for o in self
        ):
            raise UserError(
                _('Confirme individualmente los pedidos con automatizaciones para atender sus asistentes.')
            )
        self._check_type_branch()
        # IMPORTANT: do not alter picking_type_id/warehouse from the purchase type.
        # Odoo 20 remains the authority for receiving warehouse and replenishment.
        result = super().button_confirm()
        for order in self:
            action = order.action_esi_apply_type_flow() if order.state in ('purchase', 'done') else False
            if action:
                return action
        return result
