from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    esi_sale_type_id = fields.Many2one(
        'esi.sale.type',
        check_company=True,
        string='Tipo de Venta',
        domain="[('company_id', '=', company_id)]",
        copy=True,
        help=(
            'Clasificación y opciones comerciales de la sucursal. '
            'No sustituye el almacén, las rutas, el reabastecimiento ni la logística web de Odoo 20.'
        ),
    )

    esi_can_register_payment = fields.Boolean(compute='_compute_esi_can_register_payment')

    def _esi_require_type(self):
        for order in self:
            config = order.esi_sale_type_id
            if not config:
                raise UserError(_('Seleccione el Tipo de Venta antes de confirmar.'))
            config.check_access('read')
            if config.company_id != order.company_id:
                raise UserError(_('El tipo seleccionado pertenece a otra sucursal.'))
            if not config.active:
                raise UserError(_('El tipo seleccionado está archivado. Seleccione uno activo.'))

    @api.constrains('state', 'company_id', 'esi_sale_type_id')
    def _check_type_branch(self):
        for order in self:
            if order.esi_sale_type_id and order.esi_sale_type_id.company_id != order.company_id:
                raise ValidationError(_('El tipo pertenece a otra sucursal.'))
            if order.state in ('sale',):
                order._esi_require_type()

    @api.onchange('company_id')
    def _onchange_type_company(self):
        if self.esi_sale_type_id.company_id != self.company_id:
            self.esi_sale_type_id = False

    @api.depends('invoice_ids.state', 'invoice_ids.payment_state', 'esi_sale_type_id.allow_payment')
    def _compute_esi_can_register_payment(self):
        for order in self:
            order.esi_can_register_payment = bool(
                order.esi_sale_type_id.allow_payment
                and order.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted'
                    and inv.payment_state not in ('paid', 'reversed')
                    and inv.company_id == order.company_id
                    and inv.move_type == 'out_invoice'
                )
            )

    def action_esi_register_payment(self):
        self.ensure_one()
        self.check_access('read')
        if not self.esi_sale_type_id.allow_payment:
            raise UserError(_('Este tipo no permite registrar pagos desde el pedido.'))
        invoices = self.invoice_ids.filtered(
            lambda inv: inv.state == 'posted'
            and inv.payment_state not in ('paid', 'reversed')
            and inv.move_type == 'out_invoice'
            and inv.company_id == self.company_id
        )
        if not invoices:
            raise UserError(_('No hay facturas publicadas pendientes de pago.'))
        invoices.check_access('read')
        action = invoices.action_register_payment()
        action['context'] = dict(action.get('context') or {}, dont_redirect_to_payments=True)
        return action

    def _prepare_invoice(self):
        self.ensure_one()
        self._esi_require_type()
        order = self.with_company(self.company_id)
        partner = order.partner_id.commercial_partner_id
        account = partner.property_account_receivable_id or order.company_id.partner_id.property_account_receivable_id
        if not account or account.account_type != 'asset_receivable':
            raise UserError(_(
                'En %(company)s, configure una cuenta por cobrar válida para %(partner)s. '
                'Cuenta actual: %(account)s.',
                company=order.company_id.display_name, partner=partner.display_name,
                account=account.display_name or _('Sin cuenta'),
            ))
        values = super(SaleOrder, order)._prepare_invoice()
        if self.esi_sale_type_id.journal_id:
            values['journal_id'] = self.esi_sale_type_id.journal_id.id
        return values

    def action_esi_apply_type_flow(self):
        self.ensure_one()
        self.check_access('write')
        if self.state not in ('sale',):
            raise UserError(_('Primero confirme el pedido.'))
        config = self.esi_sale_type_id
        self._esi_require_type()
        config.check_access('read')
        if config.company_id != self.company_id:
            raise UserError(_('El tipo pertenece a otra sucursal.'))
        receiving_action = False
        if config.validation_picking:
            receiving_action = self._esi_validate_ready_pickings('outgoing')
            if receiving_action and config.invoice_basis == 'delivery':
                return receiving_action
        self.order_line.invalidate_recordset(['invoice_policy', 'qty_to_invoice', 'qty_invoiced'])
        self.order_line._compute_qty_to_invoice()
        self.invalidate_recordset(['invoice_ids', 'invoice_status'])
        if (config.create_invoice or config.validate_invoice) and self.invoice_status == 'to invoice':
            self._create_invoices()
        if config.validate_invoice:
            invoices = self.invoice_ids.filtered(
                lambda inv: inv.state == 'draft'
                and inv.move_type == 'out_invoice'
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
        return receiving_action or False

    def action_confirm(self):
        self._esi_require_type()
        if len(self) > 1 and any(
            o.esi_sale_type_id.validation_picking
            or o.esi_sale_type_id.create_invoice
            or o.esi_sale_type_id.validate_invoice
            for o in self
        ):
            raise UserError(
                _('Confirme individualmente los pedidos con automatizaciones para atender sus asistentes.')
            )
        self._check_type_branch()
        # IMPORTANT: do not alter warehouse_id here. Odoo 20 remains in charge
        # of website warehouse selection, routes and replenishment.
        result = super().action_confirm()
        for order in self:
            action = order.action_esi_apply_type_flow() if order.state in ('sale',) else False
            if action:
                return action
        return result
