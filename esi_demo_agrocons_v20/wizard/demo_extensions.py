from odoo import models, _


class AgroDemoWizard(models.TransientModel):
    _inherit = 'esi.agro.demo.wizard'

    def action_load(self):
        result = super().action_load()
        self.ensure_one()
        env = self.with_company(self.company_id).env
        company = self.company_id
        campaign = env['esi.agro.campaign'].search([('name','=','Verano 2025/2026'),('company_id','=',company.id)],limit=1)
        if not campaign:
            return result
        Work=env['esi.agro.work']
        Harvest=env['esi.agro.harvest']
        Transport=env['esi.agro.transport']
        Product=env['product.product']
        equipment=env['esi.agro.equipment'].search([('company_id','=',company.id)],limit=1)
        crops=Product.search([('default_code','=','DEMO-AGC-SOY-001')],limit=1)
        demo_works=[('Preparación de suelo', 'soil', 220, 180),('Siembra con sembradora', 'sowing', 350, 210),('Aplicación fitosanitaria', 'spraying', 170, 125),('Cosecha mecanizada', 'harvest', 600, 240)]
        field_yields={'NORTE':(180,2800),'SUR':(120,2350),'ESTE':(120,2500),'OESTE':(80,2250)}
        seed=Product.search([('default_code','=','DEMO-AGC-SEM-001')],limit=1)
        diesel=Product.search([('default_code','=','DEMO-AGC-DIE-001')],limit=1)
        for plan in env['esi.agro.plan'].search([('company_id','=',company.id),('campaign_id','=',campaign.id)]):
            for idx,(label,kind,service,equip_cost) in enumerate(demo_works):
                name='DEMO-%s-%s-%s' % (plan.field_id.code,kind,campaign.id)
                if not Work.search([('plan_id','=',plan.id),('name','=',name)],limit=1):
                    vals={'name':name,'company_id':company.id,'plan_id':plan.id,'kind':kind,
                          'date':'2026-%02d-10' % (1+idx),'hectares':plan.hectares,
                          'hours':round(plan.hectares/12,2),'equipment_id':equipment.id,
                          'employee_name':'Operador DEMO','service_cost':service*plan.hectares,
                          'equipment_cost':equip_cost*plan.hectares,'state':'recorded',
                          'note':'Histórico ficticio. Sin salida real de stock; validar una labor nueva para consumir.'}
                    if seed and kind=='sowing':
                        vals['input_ids']=[(0,0,{'product_id':seed.id,'quantity':round(plan.hectares*45,2),'unit_cost':12})]
                    if diesel and kind in ('soil','harvest'):
                        vals['fuel_product_id']=diesel.id
                        vals['fuel_liters']=round(plan.hectares*8,2)
                    Work.create(vals)
            code=plan.field_id.code
            ha,kg_ha=field_yields[code]
            name='DEMO-COSECHA-%s-%s' % (code,campaign.id)
            if not Harvest.search([('plan_id','=',plan.id),('name','=',name)],limit=1):
                Harvest.create({'name':name,'company_id':company.id,'plan_id':plan.id,
                    'date':'2026-04-15','hectares':ha,'gross_kg':ha*kg_ha+2000,
                    'tare_kg':2000,'humidity':12.2,'impurities':1.0,
                    'discount_pct':0.5,'product_id':crops.id if crops else False,
                    'note':'Cosecha DEMO ficticia sin entrada a inventario. No validar en base con operaciones reales.'})
            harvest=Harvest.search([('name','=',name),('plan_id','=',plan.id)],limit=1)
            if harvest and not Transport.search([('harvest_id','=',harvest.id),('name','=','DEMO-TRANSP-'+code)],limit=1):
                Transport.create({'name':'DEMO-TRANSP-'+code,'company_id':company.id,
                    'harvest_id':harvest.id,'date':'2026-04-17','tons':round(harvest.net_tons*0.7,2),
                    'cost':round(harvest.net_tons*45,2),'destination':'Silo de prueba (referencial)'})
        # Una cotización verdadera en borrador, sin entrega, factura ni asiento.
        client=env['res.partner'].search([('name','=','DEMO - Industria Aceitera del Oriente')],limit=1)
        if client and crops and not env['sale.order'].search([('client_order_ref','=','DEMO-AGC-SO-001'),('company_id','=',company.id)],limit=1):
            plan=env['esi.agro.plan'].search([('campaign_id','=',campaign.id)],limit=1)
            env['sale.order'].create({'partner_id':client.id,'company_id':company.id,
                'client_order_ref':'DEMO-AGC-SO-001','esi_agro_plan_id':plan.id,
                'order_line':[(0,0,{'product_id':crops.id,'name':'Soya en grano - DEMO','product_uom_qty':100000,'price_unit':2.5})]})
        result['params']['message']=_('Catálogo, parcelas, campañas, maquinaria, labores históricas, cosechas, transporte y cotizaciones en borrador preparados. No se validó inventario ni contabilidad.')
        return result
