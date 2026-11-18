from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


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

    def _esi_require_type(self):
        for order in self:
            config = order.esi_purchase_type_id
            if not config:
                raise UserError(_('Seleccione el Tipo de Compra antes de confirmar.'))
            config.check_access('read')
            if config.company_id != order.company_id:
                raise UserError(_('El tipo seleccionado pertenece a otra sucursal.'))
            if not config.active:
                raise UserError(_('El tipo seleccionado está archivado. Seleccione uno activo.'))

    @api.constrains('state', 'company_id', 'esi_purchase_type_id')
    def _check_type_branch(self):
        for order in self:
            if order.esi_purchase_type_id and order.esi_purchase_type_id.company_id != order.company_id:
                raise ValidationError(_('El tipo pertenece a otra sucursal.'))
            if order.state in ('purchase', 'done', 'to approve'):
                order._esi_require_type()

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
        self._esi_require_type()
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
        if self.esi_purchase_type_id.validate_invoice:
            values.setdefault('invoice_date', fields.Date.context_today(order))
        if self.esi_purchase_type_id.journal_id:
            values['journal_id'] = self.esi_purchase_type_id.journal_id.id
        return values

    def _esi_type_invoice_action(self, force_create=False):
        self.ensure_one()
        self.check_access('write')
        self._esi_require_type()
        if self.state != 'purchase':
            raise UserError(_('La compra debe estar confirmada y aprobada antes de facturar.'))
        config = self.esi_purchase_type_id
        if not (force_create or config.create_invoice or config.validate_invoice):
            return False
        # Serialize invoice creation and refresh quantities after acquiring the lock.
        self.env.cr.execute('SELECT id FROM purchase_order WHERE id = %s FOR UPDATE', [self.id])
        self.order_line.invalidate_recordset(['qty_invoiced', 'qty_to_invoice'])
        self.order_line._compute_qty_invoiced()
        self.invalidate_recordset(['invoice_ids', 'invoice_count', 'invoice_status'])
        precision = self.env['decimal.precision'].precision_get('Product Unit')
        pending = self.order_line.filtered(lambda line: not line.display_type
            and float_compare(line.qty_to_invoice, 0.0, precision_digits=precision) > 0)
        if pending:
            self.with_company(self.company_id).action_create_invoice()
            self.invalidate_recordset(['invoice_ids', 'invoice_count', 'invoice_status'])
        invoices = self.invoice_ids.filtered(lambda invoice: invoice.company_id == self.company_id
            and invoice.move_type == 'in_invoice' and invoice.state != 'cancel')
        if config.validate_invoice:
            drafts = invoices.filtered(lambda invoice: invoice.state == 'draft')
            if drafts:
                drafts.check_access('write')
                drafts.action_post()
        if invoices:
            return self.action_view_invoice(invoices)
        message = _('No hay cantidades pendientes de facturar. Si desea facturar antes de recibir, '
                    'seleccione Sobre cantidades pedidas en el tipo de compra. Si el tipo factura sobre cantidades '
                    'recibidas, registre primero la recepción real.')
        if force_create:
            raise UserError(message)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Factura pendiente'), 'message': message, 'type': 'warning', 'sticky': True,
            'next': {'type': 'ir.actions.client', 'tag': 'reload'},
        }}

    def action_esi_create_invoice(self):
        return self._esi_type_invoice_action(force_create=True)

    def _esi_validate_ready_pickings(self, code):
        if code != 'incoming':
            return super()._esi_validate_ready_pickings(code)
        self.ensure_one()
        self.check_access('write')
        for picking in self.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'incoming' and p.state not in ('done', 'cancel')):
            picking.check_access('write')
            if picking.state == 'draft':
                picking.action_confirm()
            picking.action_assign()
            moves = picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_uom_qty > 0)
            for move in moves:
                # An immediate purchase receives the ordered quantity by default.
                # Preserve quantities already entered, including partial receipts.
                if move.uom_id.is_zero(move.quantity):
                    move.quantity = move.product_uom_qty
                move.picked = True
            # Native validation enforces lots, serials, units, access and backorders.
            result = picking.button_validate()
            if picking.state != 'done':
                if isinstance(result, dict):
                    return result
                raise UserError(_('No se pudo completar la recepción %s. Revise sus cantidades y lotes.') % picking.display_name)
        return False

    def action_esi_apply_type_flow(self):
        self.ensure_one()
        self.check_access('write')
        self._esi_require_type()
        if self.state != 'purchase':
            raise UserError(_('Primero confirme y apruebe la compra.'))
        config = self.esi_purchase_type_id
        # With ordered billing, invoicing is independent from physical receiving.
        if config.invoice_basis == 'ordered':
            invoice_action = self._esi_type_invoice_action()
            if config.validation_picking:
                receiving_action = self._esi_validate_ready_pickings('incoming')
                if receiving_action:
                    return receiving_action
            return invoice_action
        if config.validation_picking:
            receiving_action = self._esi_validate_ready_pickings('incoming')
            if receiving_action:
                return receiving_action
        return self._esi_type_invoice_action()

    def button_confirm(self):
        self._esi_require_type()
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
            if action and not (isinstance(action, dict) and action.get('res_model') == 'account.move'):
                return action
        return result

    def button_approve(self, force=False):
        pending = self.filtered(lambda order: order.state == 'to approve')
        pending._esi_require_type()
        result = super().button_approve(force=force)
        if self.env.context.get('esi_skip_approval_invoice_flow'):
            return result
        for order in pending.filtered(lambda order: order.state == 'purchase'):
            action = order.action_esi_apply_type_flow()
            if action and not (isinstance(action, dict) and action.get('res_model') == 'account.move'):
                return action
        return result
