from odoo import fields, models, _
from odoo.exceptions import UserError

class AgroDemoWizard(models.TransientModel):
    _name='esi.agro.demo.wizard'
    _description='Carga segura de demo Familia Agrocons'
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    confirmation=fields.Boolean(string='Confirmo que esta es una base de pruebas')
    def action_load(self):
        self.ensure_one()
        if not self.confirmation:
            raise UserError(_('Marque la confirmación: los registros se crearán en la compañía seleccionada.'))
        company=self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active la compañía en su selector de compañías.'))
        env=self.with_company(company).env
        Partner=env['res.partner'].sudo()
        def partner(name,supplier=False):
            p=Partner.search([('name','=',name)],limit=1)
            if not p:
                p=Partner.create({'name':name,'comment':'DEMO ficticia Familia Agrocons - ESI'})
            return p
        proveedor=partner('DEMO - Agroinsumos Oriente SRL')
        partner('DEMO - Servicio Agrícola del Norte')
        comprador=partner('DEMO - Industria Aceitera del Oriente')
        category=env['product.category'].sudo().search([('name','=','DEMO | Agrocons - Insumos')],limit=1)
        if not category: category=env['product.category'].sudo().create({'name':'DEMO | Agrocons - Insumos'})
        # No se cambia el método de valoración de una categoría que ya tiene movimientos.
        existing = env['product.product'].sudo().search([('categ_id', '=', category.id)])
        if existing:
            moves = env['stock.move'].sudo().search_count([('product_id', 'in', existing.ids), ('state', '=', 'done')])
            if moves:
                method_field = 'property_cost_method' if 'property_cost_method' in category._fields else 'cost_method' if 'cost_method' in category._fields else None
                current_method = getattr(category.with_company(company), method_field) if method_field else None
                if current_method != 'average':
                    raise UserError(_('La categoría DEMO tiene movimientos existentes y no utiliza AVCO. Detenga la carga y realice una migración de valoración controlada.'))
        # AVCO solo sobre la categoría propia de la DEMO; nunca en categorías ajenas.
        if 'cost_method' in category._fields:
            category.with_company(company).write({'cost_method':'average'})
        elif 'property_cost_method' in category._fields:
            category.with_company(company).write({'property_cost_method':'average'})
        else:
            raise UserError(_('No se encontró un campo de método de costo compatible para configurar AVCO en la categoría agrícola. No se crearon datos.'))
        # Se crean fichas reales de productos; no se alteran existencias ni valoraciones.
        goods=[('SEM-001','Semilla de soya certificada (kg)',12,False,True),('FER-001','Fertilizante agrícola (kg)',8,False,True),('INO-001','Inoculante para soya (unidad)',45,False,True),('HER-001','Herbicida agrícola (litro)',65,False,True),('FUN-001','Fungicida agrícola (litro)',92,False,True),('INS-001','Insecticida agrícola (litro)',78,False,True),('DIE-001','Diésel agrícola (litro)',7,False,True),('REP-001','Repuestos agrícolas varios (unidad)',125,False,True),('SOY-001','Soya en grano cosechada (kg)',2.5,True,False)]
        Product=env['product.product'].sudo()
        for code,name,cost,sale,purchase in goods:
            sku='DEMO-AGC-'+code
            if not Product.search([('default_code','=',sku)],limit=1):
                vals={'name':name,'default_code':sku,'categ_id':category.id,'sale_ok':sale,'purchase_ok':purchase,'standard_price':cost,'list_price':round(cost*1.3,2),'description_sale':'DEMO ESI - datos ficticios'}
                if 'is_storable' in Product._fields: vals.update({'type':'consu','is_storable':True})
                Product.create(vals)
        Field=env['esi.agro.field'].sudo()
        plots=[('Campo Norte','NORTE',180,'own'),('Campo Sur','SUR',120,'own'),('Campo Este','ESTE',120,'rented'),('Campo Oeste','OESTE',80,'rented')]
        for name,code,ha,tenure in plots:
            if not Field.search([('company_id','=',company.id),('code','=',code)],limit=1):
                Field.create({'name':name,'code':code,'hectares':ha,'tenure':tenure,'company_id':company.id})
        Campaign=env['esi.agro.campaign'].sudo()
        campaigns=[('Verano 2025/2026','summer','done','2025-10-01','2026-04-30'),('Verano 2026/2027','summer','running','2026-10-01','2027-04-30')]
        for name,season,state,ds,de in campaigns:
            if not Campaign.search([('name','=',name),('company_id','=',company.id)],limit=1):
                Campaign.create({'name':name,'season':season,'state':state,'date_start':ds,'date_end':de,'company_id':company.id})
        Equipment=env['esi.agro.equipment'].sudo()
        for name,kind,ownership,rate in [('Tractor Agrocons 01','tractor','own',140),('Sembradora Agrocons 01','seeder','own',125),('Cosechadora contratada 01','harvester','rented',420),('Pulverizadora Agrocons 01','sprayer','own',110),('Camión granelero 01','truck','rented',150)]:
            if not Equipment.search([('name','=',name),('company_id','=',company.id)],limit=1):
                Equipment.create({'name':name,'kind':kind,'ownership':ownership,'hourly_cost':rate,'company_id':company.id})
        Plan=env['esi.agro.plan'].sudo()
        for camp_name,season,state,ds,de in campaigns:
            camp=Campaign.search([('name','=',camp_name),('company_id','=',company.id)],limit=1)
            for fname,code,ha,tenure in plots:
                field=Field.search([('code','=',code),('company_id','=',company.id)],limit=1)
                if not Plan.search([('field_id','=',field.id),('campaign_id','=',camp.id)],limit=1):
                    Plan.create({'name':camp_name+' / '+fname,'company_id':company.id,'campaign_id':camp.id,'field_id':field.id,'hectares':ha,'budget_per_ha':3000,'crop':'Soya','state':'harvested' if state=='done' else 'running'})
        # Para evitar asientos y ajustes involuntarios, no se confirman movimientos ni documentos.
        # Cotizaciones Odoo: se generan únicamente si el contexto tiene una lista de precios utilizable.
        currency=company.currency_id
        if not currency:
            raise UserError(_('Configure la moneda de la compañía antes de generar compras y ventas.'))
        po=env['purchase.order'].sudo()
        camp=Campaign.search([('name','=','Verano 2026/2027'),('company_id','=',company.id)],limit=1)
        plan=Plan.search([('campaign_id','=',camp.id)],limit=1)
        if plan and not po.search([('partner_ref','=','DEMO-AGC-RFQ-001'),('company_id','=',company.id)],limit=1):
            seed=Product.search([('default_code','=','DEMO-AGC-SEM-001')],limit=1)
            po.create({'partner_id':proveedor.id,'company_id':company.id,'partner_ref':'DEMO-AGC-RFQ-001','esi_agro_plan_id':plan.id,'order_line':[(0,0,{'name':seed.display_name,'product_id':seed.id,'product_qty':2000,'price_unit':12,'uom_id':seed.uom_id.id})]})
        return {'type':'ir.actions.client','tag':'display_notification','params':{'title':_('Demo agrícola cargada'),'message':_('Parcelas, campañas, productos, maquinaria y una solicitud de compra en borrador. No se modificó stock.'),'type':'success','sticky':False}}
