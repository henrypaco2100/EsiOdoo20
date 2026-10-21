from collections import defaultdict
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    esi_cost_currency_id = fields.Many2one(related='company_id.currency_id')
    esi_estimated_unit_cost = fields.Monetary(compute='_compute_esi_material_cost', currency_field='esi_cost_currency_id', string='Costo estimado / unidad', groups='mrp.group_mrp_manager')
    esi_estimated_cost = fields.Monetary(compute='_compute_esi_material_cost', currency_field='esi_cost_currency_id', string='Subtotal estimado', groups='mrp.group_mrp_manager')

    @api.depends('product_id', 'product_uom_qty', 'uom_id', 'company_id', 'product_id.standard_price')
    @api.depends_context('company')
    def _compute_esi_material_cost(self):
        for move in self:
            product = move.product_id.with_company(move.company_id)
            unit = product.uom_id._compute_price(product.standard_price, move.uom_id) if product and move.uom_id else 0
            move.esi_estimated_unit_cost = unit
            move.esi_estimated_cost = unit * move.product_uom_qty


class PurchaseLine(models.Model):
    _inherit = 'purchase.order.line'

    esi_material_production_id = fields.Many2one('mrp.production', string='OF solicitante', check_company=True, copy=False, index=True, readonly=True)


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_purchase_revision = fields.Integer(copy=False, readonly=True)
    esi_display_total_qty = fields.Float(compute='_compute_esi_display_total', string='Cantidad total a fabricar', digits='Product Unit')

    @api.depends('state', 'esi_variant_line_mode', 'esi_output_total', 'esi_total_output_qty')
    def _compute_esi_display_total(self):
        for mo in self:
            mo.esi_display_total_qty = mo.esi_output_total if mo.state == 'draft' and mo.esi_variant_line_mode else mo.esi_total_output_qty

    esi_budget_currency_id = fields.Many2one(related='company_id.currency_id')
    esi_material_estimate = fields.Monetary(compute='_compute_esi_material_estimate', currency_field='esi_budget_currency_id', string='Materiales: costo estimado', groups='mrp.group_mrp_manager')

    @api.depends('move_raw_ids.esi_estimated_cost', 'move_raw_ids.state')
    def _compute_esi_material_estimate(self):
        for mo in self:
            mo.esi_material_estimate = sum(mo.move_raw_ids.filtered(lambda m: m.state != 'cancel').mapped('esi_estimated_cost'))

    def _esi_purchase_shortages(self):
        """One demand per product, in its stock UoM, at this OF's source.

        Reservations of this OF are already excluded from free_qty. Deduct
        both exactly once. Open linked purchases include draft RFQs, preventing
        a second wizard from buying the same need again.
        """
        self.ensure_one()
        self.check_access('read')
        if self.company_id not in self.env.companies:
            raise UserError(_('Active la compañía de la orden.'))
        if self.state in ('done', 'cancel'):
            return []
        moves = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id.is_storable)
        # Draft MOs have not generated stock moves. Estimate the requirements
        # from the size-specific shared recipe, without confirming the order.
        draft_demand = defaultdict(float)
        if self.state == 'draft' and self.esi_variant_line_mode:
            bom = self.esi_plan_bom_id
            if not bom or not self.esi_output_line_ids:
                raise UserError(_('Seleccione una receta y las cantidades por talla, y guarde la orden antes de comprar.'))
            for output in self.esi_output_line_ids.filtered(lambda l: l.quantity > 0):
                product = output.product_id
                factor = product.uom_id._compute_quantity(output.quantity, bom.uom_id, round=False) / bom.product_qty
                for component in bom.bom_line_ids:
                    if component._skip_bom_line(product) or not component.product_id.is_storable:
                        continue
                    draft_demand[component.product_id.id] += component.uom_id._compute_quantity(component.product_qty * factor, component.product_id.uom_id, round=False)
        elif self.state == 'draft' and not moves:
            raise UserError(_('Configure los componentes y guarde la orden antes de solicitar la compra.'))
        if any(m.location_id != self.location_src_id for m in moves):
            raise UserError(_('Los componentes tienen ubicaciones de origen diferentes. Revise el abastecimiento por ubicación antes de solicitar la compra.'))
        demand, reserved, pending = defaultdict(float), defaultdict(float), defaultdict(float)
        demand.update(draft_demand)
        for move in moves:
            product = move.product_id
            demand[product.id] += move.uom_id._compute_quantity(move.product_uom_qty, product.uom_id, round=False)
            reserved[product.id] += move.uom_id._compute_quantity(move.quantity, product.uom_id, round=False)
        purchases = self.env['purchase.order.line'].search([
            '|', ('esi_material_production_id', '=', self.id), ('move_dest_ids', 'in', moves.ids), ('company_id', '=', self.company_id.id),
            ('order_id.state', 'in', ['draft', 'sent', 'to approve', 'purchase', 'done'])])
        for line in purchases:
            pending[line.product_id.id] += line.uom_id._compute_quantity(max(0, line.product_qty - line.qty_received), line.product_id.uom_id, round=False)
        rows = []
        products = moves.product_id
        if draft_demand:
            products |= self.env['product.product'].browse(list(draft_demand))
        for product in products:
            free = max(0, product.with_company(self.company_id).with_context(location=self.location_src_id.id).free_qty)
            shortage = max(0, demand[product.id] - reserved[product.id] - free - pending[product.id])
            rows.append({'product': product, 'required': demand[product.id], 'reserved': reserved[product.id],
                'free': free, 'pending': pending[product.id], 'shortage': shortage})
        return rows

    def action_esi_material_purchase(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('purchase.group_purchase_user') or not self.env.user.has_group('mrp.group_mrp_user'):
            raise UserError(_('Se requieren permisos de Compras y Fabricación.'))
        if self.state not in ('draft', 'confirmed', 'progress'):
            raise UserError(_('La orden está cerrada y no admite solicitudes.'))
        rows = self._esi_purchase_shortages()
        lines = []
        for row in rows:
            product = row['product']
            if product.uom_id.is_zero(row['shortage']):
                continue
            sellers = product.with_company(self.company_id).seller_ids.filtered(lambda s:
                (not s.company_id or s.company_id == self.company_id) and (not s.product_id or s.product_id == product))
            lines.append(Command.create({'product_id': product.id, 'required_qty': row['required'],
                'reserved_qty': row['reserved'], 'free_qty': row['free'], 'pending_qty': row['pending'],
                'quantity': row['shortage'], 'supplier_id': sellers[:1].partner_id.id}))
        if not lines:
            raise UserError(_('No hay faltantes por comprar. La necesidad está cubierta por reservas, stock libre o compras vinculadas.'))
        wizard = self.env['esi.material.purchase'].create({'production_id': self.id, 'line_ids': lines})
        return {'type': 'ir.actions.act_window', 'res_model': wizard._name, 'res_id': wizard.id,
            'name': _('Comprar materiales faltantes'), 'view_mode': 'form', 'target': 'new'}

    def action_esi_material_purchases(self):
        self.ensure_one()
        self.check_access('read')
        orders = self.env['purchase.order.line'].search(['|', ('esi_material_production_id', '=', self.id), ('move_dest_ids', 'in', self.move_raw_ids.ids), ('company_id', '=', self.company_id.id)]).order_id
        return {'type': 'ir.actions.act_window', 'name': _('Compras de materiales'), 'res_model': 'purchase.order',
            'view_mode': 'list,form', 'domain': [('id', 'in', orders.ids)]}


class MaterialPurchase(models.TransientModel):
    _name = 'esi.material.purchase'
    _description = 'Solicitud de materiales faltantes'
    _check_company_auto = True

    production_id = fields.Many2one('mrp.production', required=True, readonly=True, check_company=True)
    company_id = fields.Many2one(related='production_id.company_id')
    line_ids = fields.One2many('esi.material.purchase.line', 'wizard_id')

    def action_create_rfq(self):
        self.ensure_one()
        self.check_access('write')
        mo = self.production_id
        mo.check_access('write')
        if not self.env.user.has_group('mrp.group_mrp_user') or not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_('Se requieren permisos de Compras y Fabricación.'))
        # Updating a revision forces a serialization retry for concurrent
        # requests under PostgreSQL repeatable-read, before buying twice.
        mo.write({'esi_purchase_revision': mo.esi_purchase_revision + 1})
        mo.flush_recordset(['esi_purchase_revision'])
        if mo.state not in ('draft', 'confirmed', 'progress'):
            raise UserError(_('La orden está cerrada y no admite solicitudes.'))
        warehouse = mo.warehouse_id
        if not warehouse or warehouse.company_id != mo.company_id or mo.location_src_id != warehouse.lot_stock_id:
            raise UserError(_('Este asistente requiere el stock principal del almacén como origen. Para ubicaciones especiales use las rutas de abastecimiento.'))
        latest = {r['product'].id: r for r in mo._esi_purchase_shortages()}
        grouped = defaultdict(list)
        seen = set()
        for line in self.line_ids.filtered('selected'):
            if line.product_id.id in seen:
                raise UserError(_('No repita un componente.'))
            seen.add(line.product_id.id)
            row = latest.get(line.product_id.id)
            if not row or line.product_id.uom_id.is_zero(row['shortage']):
                continue
            supplier = line.supplier_id
            supplier.check_access('read')
            if not supplier or (supplier.company_id and supplier.company_id != mo.company_id):
                raise UserError(_('Seleccione un proveedor válido para cada material.'))
            if not line.product_id.purchase_ok:
                raise UserError(_('Active Compras en el producto %s.', line.product_id.display_name))
            grouped[supplier.id].append(row)
        if not grouped:
            raise UserError(_('No hay materiales seleccionados pendientes de compra.'))
        orders = self.env['purchase.order']
        for partner_id, rows in grouped.items():
            order = self.env['purchase.order'].with_company(mo.company_id).create({
                'partner_id': partner_id, 'company_id': mo.company_id.id,
                'origin': mo.name, 'picking_type_id': warehouse.in_type_id.id})
            for row in rows:
                product = row['product']
                self.env['purchase.order.line'].with_company(mo.company_id).create({
                    'order_id': order.id, 'product_id': product.id,
                    'product_qty': row['shortage'], 'uom_id': product.uom_id.id,
                    'esi_material_production_id': mo.id})
            orders |= order
        return {'type': 'ir.actions.act_window', 'name': _('Solicitudes de presupuesto'),
            'res_model': 'purchase.order', 'view_mode': 'list,form', 'domain': [('id', 'in', orders.ids)]}


class MaterialPurchaseLine(models.TransientModel):
    _name = 'esi.material.purchase.line'
    _description = 'Material pendiente de compra'

    wizard_id = fields.Many2one('esi.material.purchase', required=True, ondelete='cascade')
    selected = fields.Boolean(default=True, string='Comprar')
    product_id = fields.Many2one('product.product', required=True, readonly=True, string='Material')
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    required_qty = fields.Float(readonly=True, string='Necesario')
    reserved_qty = fields.Float(readonly=True, string='Reservado / recogido')
    free_qty = fields.Float(readonly=True, string='Stock libre')
    pending_qty = fields.Float(readonly=True, string='Compra pendiente')
    quantity = fields.Float(readonly=True, string='Faltante a comprar')
    supplier_id = fields.Many2one('res.partner', string='Proveedor')
