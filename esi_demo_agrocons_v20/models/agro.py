from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AgroField(models.Model):
    _name = 'esi.agro.field'
    _description = 'Parcela agrícola'
    _order = 'name'
    name = fields.Char(required=True)
    code = fields.Char(index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    hectares = fields.Float(string='Hectáreas', required=True)
    tenure = fields.Selection([('own','Propio'),('rented','Alquilado')], default='own', required=True)
    owner_id = fields.Many2one('res.partner', string='Propietario')
    note = fields.Text()
    _sql_constraints = [('positive_ha','CHECK(hectares > 0)','La superficie debe ser positiva.')]

class AgroCampaign(models.Model):
    _name = 'esi.agro.campaign'
    _description = 'Campaña agrícola'
    _order = 'name desc'
    name = fields.Char(required=True)
    season = fields.Selection([('summer','Verano'),('winter','Invierno')], required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    state = fields.Selection([('draft','Planificada'),('running','En proceso'),('done','Finalizada')], default='draft', required=True)
    note = fields.Text()

class AgroEquipment(models.Model):
    _name = 'esi.agro.equipment'
    _description = 'Equipo o maquinaria agrícola'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    kind = fields.Selection([('tractor','Tractor'),('seeder','Sembradora'),('harvester','Cosechadora'),('sprayer','Pulverizadora'),('truck','Camión'),('other','Otro')], required=True, default='tractor')
    ownership = fields.Selection([('own','Propia'),('rented','Contratada')], default='own')
    partner_id = fields.Many2one('res.partner', string='Contratista')
    license_plate = fields.Char(string='Identificación')
    hourly_cost = fields.Float(string='Costo por hora estimado')
    note = fields.Text()

class AgroPlan(models.Model):
    _name = 'esi.agro.plan'
    _description = 'Plan de siembra por parcela y campaña'
    _order = 'campaign_id,field_id'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    campaign_id = fields.Many2one('esi.agro.campaign', required=True)
    field_id = fields.Many2one('esi.agro.field', required=True)
    hectares = fields.Float(required=True)
    crop = fields.Char(default='Soya', required=True)
    variety = fields.Char(string='Variedad de semilla')
    planned_date = fields.Date(string='Fecha de siembra prevista')
    actual_date = fields.Date(string='Fecha de siembra real')
    budget_per_ha = fields.Float(string='Presupuesto por hectárea (Bs)')
    budget_total = fields.Float(string='Presupuesto total', compute='_calc', store=True)
    work_ids = fields.One2many('esi.agro.work','plan_id',string='Labores')
    harvest_ids = fields.One2many('esi.agro.harvest','plan_id',string='Cosechas')
    work_cost = fields.Float(compute='_calc',store=True, string='Costo operativo')
    harvested_tons = fields.Float(compute='_calc',store=True,string='Toneladas registradas')
    cost_per_ha = fields.Float(compute='_calc',store=True,string='Costo por ha')
    cost_per_ton = fields.Float(compute='_calc',store=True,string='Costo por tonelada')
    state = fields.Selection([('draft','Planificación'),('running','En ejecución'),('harvested','Cosechada')], default='draft')
    @api.depends('hectares','budget_per_ha','work_ids.total_cost','harvest_ids.net_tons')
    def _calc(self):
        for r in self:
            r.budget_total = r.hectares*r.budget_per_ha
            r.work_cost = sum(r.work_ids.mapped('total_cost'))
            r.harvested_tons = sum(r.harvest_ids.mapped('net_tons'))
            r.cost_per_ha = r.work_cost/r.hectares if r.hectares else 0
            r.cost_per_ton = r.work_cost/r.harvested_tons if r.harvested_tons else 0
    @api.constrains('hectares','field_id')
    def _check_area(self):
        for r in self:
            if r.hectares <= 0 or r.hectares > r.field_id.hectares:
                raise ValidationError(_('La superficie debe ser positiva y no exceder la parcela.'))

class AgroWork(models.Model):
    _name = 'esi.agro.work'
    _description = 'Bitácora de labores agrícolas'
    _order = 'date desc,id desc'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    plan_id = fields.Many2one('esi.agro.plan', required=True, ondelete='cascade')
    date = fields.Date(default=fields.Date.context_today, required=True)
    kind = fields.Selection([('soil','Preparación'),('sowing','Siembra'),('spraying','Aplicación'),('fertilizer','Fertilización'),('harvest','Cosecha'),('transport','Transporte'),('maintenance','Mantenimiento'),('other','Otra')],required=True,default='sowing')
    hectares = fields.Float(string='Hectáreas trabajadas')
    hours = fields.Float(string='Horas máquina')
    equipment_id = fields.Many2one('esi.agro.equipment')
    employee_name = fields.Char(string='Operador / responsable')
    contractor_id = fields.Many2one('res.partner', string='Contratista')
    service_cost = fields.Float(string='Costo servicios y mano de obra')
    equipment_cost = fields.Float(string='Costo maquinaria')
    input_ids = fields.One2many('esi.agro.work.input','work_id',string='Insumos utilizados')
    input_cost = fields.Float(string='Costo insumos', compute='_compute_cost',store=True)
    total_cost = fields.Float(string='Costo total operativo',compute='_compute_cost',store=True)
    state = fields.Selection([('draft','Borrador'),('recorded','Registrada')],default='draft')
    note = fields.Text()
    purchase_order_id = fields.Many2one('purchase.order',string='Compra vinculada')
    @api.depends('input_ids.quantity','input_ids.unit_cost','service_cost','equipment_cost')
    def _compute_cost(self):
        for r in self:
            r.input_cost = sum(x.quantity*x.unit_cost for x in r.input_ids)
            r.total_cost = r.input_cost+r.service_cost+r.equipment_cost
    def action_record(self):
        for r in self:
            if r.state != 'draft':
                continue
            r.state='recorded'
        # Solo bitácora; las existencias reales se consumen mediante transferencias Odoo.
    def action_open_stock_moves(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','name':_('Movimientos de inventario'),'res_model':'stock.move','view_mode':'list,form','domain':[('reference','ilike',self.name)]}

class AgroWorkInput(models.Model):
    _name = 'esi.agro.work.input'
    _description = 'Insumo usado en una labor'
    work_id = fields.Many2one('esi.agro.work',required=True,ondelete='cascade')
    product_id = fields.Many2one('product.product',required=True,domain=[('purchase_ok','=',True)])
    quantity = fields.Float(required=True,default=1)
    unit_cost = fields.Float(string='Costo unitario estimado')
    @api.onchange('product_id')
    def _onchange_product(self):
        for r in self:
            if r.product_id:
                r.unit_cost = r.product_id.standard_price
    @api.constrains('quantity')
    def _check_quantity(self):
        if any(x.quantity <= 0 for x in self):
            raise ValidationError(_('La cantidad de insumos debe ser positiva.'))

class AgroHarvest(models.Model):
    _name = 'esi.agro.harvest'
    _description = 'Cosecha y pesaje de grano'
    _order = 'date desc,id desc'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s:s.env.company)
    plan_id = fields.Many2one('esi.agro.plan',required=True)
    date = fields.Date(default=fields.Date.context_today,required=True)
    equipment_id = fields.Many2one('esi.agro.equipment',string='Cosechadora')
    operator = fields.Char()
    hours = fields.Float(string='Horas')
    hectares = fields.Float(string='Superficie cosechada (ha)')
    gross_kg = fields.Float(string='Peso bruto (kg)')
    tare_kg = fields.Float(string='Tara (kg)')
    net_kg = fields.Float(string='Peso físico neto (kg)',compute='_calc',store=True)
    humidity = fields.Float(string='Humedad (%)')
    impurities = fields.Float(string='Impurezas (%)')
    discount_pct = fields.Float(string='Descuento comercial supuesto (%)')
    commercial_kg = fields.Float(string='Peso comercial teórico (kg)',compute='_calc',store=True)
    net_tons = fields.Float(string='Toneladas físicas',compute='_calc',store=True)
    yield_t_ha = fields.Float(string='Rendimiento (t/ha)',compute='_calc',store=True)
    lot_id = fields.Many2one('stock.lot',string='Lote Odoo')
    picking_id = fields.Many2one('stock.picking',string='Recepción de grano Odoo')
    note = fields.Text()
    @api.depends('gross_kg','tare_kg','hectares','discount_pct')
    def _calc(self):
        for r in self:
            r.net_kg = max(r.gross_kg-r.tare_kg,0)
            r.net_tons = r.net_kg/1000
            r.yield_t_ha = r.net_tons/r.hectares if r.hectares else 0
            r.commercial_kg = r.net_kg*(1-r.discount_pct/100)
    @api.constrains('gross_kg','tare_kg','hectares','humidity','impurities','discount_pct')
    def _check_data(self):
        for r in self:
            if r.gross_kg < 0 or r.tare_kg < 0 or r.tare_kg > r.gross_kg or r.hectares < 0 or any(v<0 or v>100 for v in (r.humidity,r.impurities,r.discount_pct)):
                raise ValidationError(_('Revise pesos, hectáreas y porcentajes de calidad.'))

class AgroTransport(models.Model):
    _name='esi.agro.transport'
    _description='Transporte agrícola'
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',default=lambda s:s.env.company,required=True)
    date=fields.Date(default=fields.Date.context_today)
    harvest_id=fields.Many2one('esi.agro.harvest')
    partner_id=fields.Many2one('res.partner',string='Transportista')
    truck=fields.Char(string='Camión / placa')
    tons=fields.Float(string='Toneladas transportadas')
    cost=fields.Float(string='Costo de transporte')
    destination=fields.Char(string='Destino')
    note=fields.Text()

class PurchaseOrder(models.Model):
    _inherit='purchase.order'
    esi_agro_plan_id=fields.Many2one('esi.agro.plan',string='Plan agrícola ESI',index=True)

class SaleOrder(models.Model):
    _inherit='sale.order'
    esi_agro_plan_id=fields.Many2one('esi.agro.plan',string='Origen agrícola ESI',index=True)

class StockPicking(models.Model):
    _inherit='stock.picking'
    esi_agro_plan_id=fields.Many2one('esi.agro.plan',string='Plan agrícola ESI',index=True)
