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
                    and inv.company_id == order.company_id
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
        self.ensure_one()
        order = self.with_company(self.company_id)
        partner = order.partner_id.commercial_partner_id
        account = partner.property_account_payable_id or order.company_id.partner_id.property_account_payable_id
        if not account or account.account_type != 'liability_payable':
            raise UserError(_(
                'En %(company)s, configure una cuenta por pagar válida para %(partner)s. '
                'Cuenta actual: %(account)s.',
                company=order.company_id.display_name, partner=partner.display_name,
                account=account.display_name or _('Sin cuenta'),
            ))
        values = super(PurchaseOrder, order)._prepare_invoice()
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
        if (config.create_invoice or config.validate_invoice) and self.invoice_status == 'to invoice':
            self.action_create_invoice()
        if config.validate_invoice:
            invoices = self.invoice_ids.filtered(
                lambda inv: inv.state == 'draft'
                and inv.move_type == 'in_invoice'
                and inv.company_id == self.company_id
            )
            invoices.check_access('write')
            if invoices:
                invoices.action_post()
        if (config.create_invoice or config.validate_invoice) and not self.invoice_ids.filtered(
            lambda inv: inv.state != 'cancel' and inv.company_id == self.company_id
        ):
            message = _('Factura pendiente: no hay cantidades facturables. Revise la política de facturación y valide la recepción o entrega si corresponde. Luego pulse Aplicar opciones del tipo.')
            self.message_post(body=message)
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Factura pendiente'), 'message': message, 'type': 'warning', 'sticky': True,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }}
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
        result = super(PurchaseOrder, self.with_context(esi_skip_approval_invoice_flow=True)).button_confirm()
        for order in self:
            action = order.action_esi_apply_type_flow() if order.state in ('purchase', 'done') else False
            if action:
                return action
        return result

    def button_approve(self, force=False):
        pending = self.filtered(lambda order: order.state == 'to approve')
        result = super().button_approve(force=force)
        if self.env.context.get('esi_skip_approval_invoice_flow'):
            return result
        for order in pending.filtered(lambda order: order.state == 'purchase'):
            action = order.action_esi_apply_type_flow()
            if action:
                return action
        return result
