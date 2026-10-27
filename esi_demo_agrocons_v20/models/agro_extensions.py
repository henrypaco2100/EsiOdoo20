from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AgroField(models.Model):
    _inherit = 'esi.agro.field'
    rent_rate_ha = fields.Float(string='Alquiler por hectárea/campaña (Bs)')
    rent_contract = fields.Char(string='Referencia de contrato')
    rent_until = fields.Date(string='Vencimiento del contrato')


class AgroEquipment(models.Model):
    _inherit = 'esi.agro.equipment'
    maintenance_ids = fields.One2many('esi.agro.maintenance', 'equipment_id', string='Mantenimientos')
    next_service_date = fields.Date(string='Próximo mantenimiento')
    fuel_total = fields.Float(string='Combustible consumido (L)', compute='_calc_fuel')

    def _calc_fuel(self):
        for eq in self:
            eq.fuel_total = sum(self.env['esi.agro.work'].search([
                ('equipment_id', '=', eq.id), ('state', '=', 'recorded')]).mapped('fuel_liters'))


class AgroMaintenance(models.Model):
    _name = 'esi.agro.maintenance'
    _description = 'Mantenimiento de maquinaria agrícola'
    _order = 'date desc, id desc'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    equipment_id = fields.Many2one('esi.agro.equipment', required=True, ondelete='cascade')
    date = fields.Date(required=True, default=fields.Date.context_today)
    hours_meter = fields.Float(string='Horómetro')
    cost = fields.Monetary(currency_field='currency_id', string='Costo (moneda de empresa)')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    vendor_id = fields.Many2one('res.partner', string='Proveedor')
    next_date = fields.Date(string='Siguiente revisión')
    description = fields.Text()


class AgroPlan(models.Model):
    _inherit = 'esi.agro.plan'
    rent_cost = fields.Float(string='Alquiler de tierra previsto/real (Bs)')
    transport_cost = fields.Float(string='Transporte agregado (Bs)', compute='_compute_transport_cost')
    real_total_cost = fields.Float(string='Costo operativo total (Bs)', compute='_compute_transport_cost')
    budget_variance = fields.Float(string='Variación presupuesto (Bs)', compute='_compute_transport_cost')
    planned_yield = fields.Float(string='Rendimiento planificado (t/ha)')
    alert_notes = fields.Text(string='Alertas de insumos')

    @api.depends('work_cost', 'rent_cost', 'budget_total')
    def _compute_transport_cost(self):
        Transport = self.env['esi.agro.transport']
        for r in self:
            r.transport_cost = sum(Transport.search([('harvest_id.plan_id', '=', r.id)]).mapped('cost'))
            r.real_total_cost = r.work_cost + r.rent_cost + r.transport_cost
            r.budget_variance = r.real_total_cost - r.budget_total

    def action_check_inputs(self):
        for plan in self:
            missing=[]
            for work in plan.work_ids.filtered(lambda w: w.state == 'draft'):
                for line in work.input_ids:
                    available = line.product_id.with_company(plan.company_id).qty_available
                    if available < line.quantity:
                        missing.append('%s: solicitado %.2f, disponible %.2f' % (line.product_id.display_name, line.quantity, available))
            plan.alert_notes = '\n'.join(missing) or _('No se detectaron faltantes en las labores borrador (disponibilidad general).')
        return {'type':'ir.actions.client','tag':'display_notification','params':{
            'title':_('Verificación de insumos'), 'message':self[:1].alert_notes or '', 'type':'warning' if any('solicitado' in (r.alert_notes or '') for r in self) else 'success', 'sticky':True}}


class AgroWork(models.Model):
    _inherit = 'esi.agro.work'
    fuel_liters = fields.Float(string='Diésel consumido (L)')
    stock_move_ids = fields.One2many('stock.move', 'esi_agro_work_id', string='Movimientos de consumo', readonly=True)
    stock_consumed = fields.Boolean(string='Consumo contabilizado en inventario', readonly=True, copy=False)
    execution_date = fields.Date(string='Fecha programada')
    fuel_product_id = fields.Many2one('product.product', string='Combustible (opcional)')

    @api.constrains('fuel_liters')
    def _check_fuel(self):
        for rec in self:
            if rec.fuel_liters < 0:
                raise ValidationError(_('El consumo de combustible no puede ser negativo.'))

    def action_consume_inputs(self):
        """Explicit stock operation, never triggered by demo loading or normal record action.
        Uses a production virtual location and real moves in Odoo's standard stock ledger.
        """
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Solo responsables de Inventario pueden validar consumos.'))
        StockMove = self.env['stock.move']
        for work in self:
            if work.stock_consumed or work.stock_move_ids:
                raise UserError(_('Esta labor ya tiene movimientos de consumo. No se puede repetir.'))
            if work.state != 'recorded':
                raise UserError(_('Primero debe registrar la labor.'))
            company = work.company_id
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
            destination = self.env['stock.location'].search([('usage','=','production'),('company_id','in',[company.id,False])], limit=1)
            if not warehouse or not destination:
                raise UserError(_('Falta almacén o ubicación virtual de producción. Configure Inventario.'))
            lines = [(l.product_id, l.quantity) for l in work.input_ids]
            if work.fuel_product_id and work.fuel_liters:
                if any(p.id == work.fuel_product_id.id for p, q in lines):
                    raise UserError(_('El combustible ya está incluido como insumo: evite duplicar su consumo.'))
                lines.append((work.fuel_product_id, work.fuel_liters))
            if not lines:
                raise UserError(_('No hay insumos que consumir.'))
            for product, qty in lines:
                if not product.is_storable:
                    raise UserError(_('El producto %s no tiene seguimiento de existencias.') % product.display_name)
                if product.tracking != 'none':
                    raise UserError(_('Para este flujo use insumos sin trazabilidad por lote: %s.') % product.display_name)
                available = self.env['stock.quant']._get_available_quantity(product, warehouse.lot_stock_id)
                if available + 1e-6 < qty:
                    raise UserError(_('Existencia insuficiente de %s: %.2f disponible; %.2f requerido.') % (product.display_name, available, qty))
            moves = StockMove.browse()
            for product, qty in lines:
                move = StockMove.with_company(company).create({
                    'name':'AGRO / %s / %s' % (work.plan_id.name, work.name),
                    'company_id':company.id,'product_id':product.id,
                    'product_uom':product.uom_id.id,'product_uom_qty':qty,
                    'location_id':warehouse.lot_stock_id.id,'location_dest_id':destination.id,
                    'esi_agro_work_id':work.id,
                })
                move._action_confirm()
                self.env['stock.move.line'].create({
                    'move_id':move.id,'product_id':product.id,'product_uom_id':product.uom_id.id,
                    'location_id':warehouse.lot_stock_id.id,'location_dest_id':destination.id,
                    'quantity':qty,'company_id':company.id,
                })
                moves |= move
            moves._action_done()
            # Congelar el costo histórico utilizado en la labor al momento del consumo.
            for line in work.input_ids:
                line.unit_cost = line.product_id.with_company(company).standard_price
            work.write({'stock_consumed':True})
        return True


class StockMove(models.Model):
    _inherit = 'stock.move'
    esi_agro_work_id = fields.Many2one('esi.agro.work', string='Consumo de labor agrícola', index=True, copy=False)
    esi_agro_harvest_id = fields.Many2one('esi.agro.harvest', string='Cosecha agrícola', index=True, copy=False)


class AgroHarvest(models.Model):
    _inherit = 'esi.agro.harvest'
    stock_move_ids = fields.One2many('stock.move', 'esi_agro_harvest_id', string='Entradas de grano', readonly=True)
    stock_received = fields.Boolean(string='Grano ingresado al inventario', readonly=True, copy=False)
    product_id = fields.Many2one('product.product', string='Producto cosechado')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén de destino')
    estimated_unit_cost = fields.Float(string='Costo operativo estimado/kg', compute='_compute_estimated_unit_cost')

    @api.depends('plan_id.work_cost','plan_id.harvested_tons')
    def _compute_estimated_unit_cost(self):
        for r in self:
            r.estimated_unit_cost = (r.plan_id.work_cost / (r.plan_id.harvested_tons * 1000.0)) if r.plan_id.harvested_tons else 0.0

    def action_receive_grain(self):
        """Post a real incoming stock move into the existing Odoo warehouse, once only.
        Does not force accounting/AVCO cost: that requires company-specific valuation setup.
        """
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('Solo responsables de Inventario pueden validar cosechas.'))
        for harvest in self:
            if harvest.stock_received or harvest.stock_move_ids:
                raise UserError(_('La cosecha ya registra una entrada de inventario.'))
            product = harvest.product_id
            if not product or not product.is_storable or harvest.net_kg <= 0:
                raise UserError(_('Seleccione un producto almacenable y registre un peso neto positivo.'))
            if product.tracking != 'lot':
                raise UserError(_('Configure el producto de soya con seguimiento por lotes antes de ingresar grano.'))
            warehouse = harvest.warehouse_id or self.env['stock.warehouse'].search([('company_id','=',harvest.company_id.id)],limit=1)
            source = self.env['stock.location'].search([('usage','=','production'),('company_id','in',[harvest.company_id.id,False])],limit=1)
            if not warehouse or not source:
                raise UserError(_('Falta almacén o ubicación virtual de producción.'))
            lot = harvest.lot_id
            if not lot:
                lot = self.env['stock.lot'].create({'name':'AGC-%s-%s' % (harvest.plan_id.field_id.code or 'CAMPO',harvest.id), 'product_id':product.id,'company_id':harvest.company_id.id})
                harvest.lot_id = lot.id
            move = self.env['stock.move'].with_company(harvest.company_id).create({
                'name':'COSECHA / %s' % harvest.name,'company_id':harvest.company_id.id,
                'product_id':product.id,'product_uom':product.uom_id.id,
                'product_uom_qty':harvest.net_kg,
                'location_id':source.id,'location_dest_id':warehouse.lot_stock_id.id,
                'esi_agro_harvest_id':harvest.id,
            })
            move._action_confirm()
            self.env['stock.move.line'].create({
                'move_id':move.id,'product_id':product.id,'product_uom_id':product.uom_id.id,
                'location_id':source.id,'location_dest_id':warehouse.lot_stock_id.id,
                'lot_id':lot.id,'quantity':harvest.net_kg,'company_id':harvest.company_id.id,
            })
            move._action_done()
            harvest.stock_received = True
        return True
