import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RealRecipe(models.Model):
    _name = 'tosscano.recipe.config'
    _description = 'Receta de Tosscano con materiales migrados'
    _rec_name = 'code'

    migration_id = fields.Many2one('tosscano.migration', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='migration_id.factory_id', store=True)
    code = fields.Char(required=True, readonly=True)
    name = fields.Char(readonly=True)
    template_ids = fields.Many2many('product.template', string='Productos terminados')
    line_ids = fields.One2many('tosscano.recipe.component', 'recipe_id', string='Componentes de la ficha')
    reviewed = fields.Boolean(string='Correspondencias y aplicación revisadas')
    minutes_per_pair = fields.Float(string='Minutos por par y centro', default=1,
        help='Valor provisional inicial. Ajuste al tiempo real antes de planificar producción.')
    result = fields.Text(readonly=True)

    def action_create_bom(self):
        self.ensure_one()
        migration = self.migration_id
        migration._lock()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requieren permisos de administrador de Fabricación.'))
        if 'esi_center_route_ids' not in self.env['mrp.bom']._fields:
            raise UserError(_('Actualice ESI Calzados: falta Recorrido por centros.'))
        if not self.reviewed:
            raise UserError(_('Revise los productos y las cantidades en la unidad del inventario y marque Correspondencias y aplicación revisadas.'))
        if not self.template_ids:
            raise UserError(_('Seleccione el producto terminado migrado al que corresponde esta ficha.'))
        if not math.isfinite(self.minutes_per_pair) or self.minutes_per_pair <= 0:
            raise UserError(_('Indique un tiempo positivo por centro.'))
        data = migration._source()
        allowed_templates = {migration._ref(r['key']).id for r in data['finished'] if migration._ref(r['key'])}
        allowed_products = {migration._ref(r['key']).id for r in data['materials'] if migration._ref(r['key'])}
        if any(t.id not in allowed_templates for t in self.template_ids):
            raise UserError(_('Seleccione únicamente productos terminados vinculados a esta migración.'))
        source = [r for r in data['components'] if r['recipe']==self.code and r['qty_per_pair']>0]
        if len(source)!=len(self.line_ids) or sorted(r['row'] for r in source)!=sorted(self.line_ids.mapped('source_row')):
            raise UserError(_('Faltan líneas de la ficha. Prepare nuevamente las correspondencias.'))
        values = []
        for line in self.line_ids:
            product = line.product_id
            if not product or product.id not in allowed_products:
                raise UserError(_('Seleccione un componente migrado para %s.',line.source_name))
            if product.company_id != self.company_id or not product.esi_component_ok or not product.active:
                raise UserError(_('Revise la sucursal, estado y marca Componentes de %s.',product.display_name))
            if not math.isfinite(line.inventory_qty_per_pair) or line.inventory_qty_per_pair <= 0:
                raise UserError(_('Indique la cantidad por par en %s para %s.',product.uom_id.name,line.source_name))
            values.append((0,0,{'product_id':product.id,'uom_id':product.uom_id.id,
                               'product_qty':line.inventory_qty_per_pair}))
        centers = []
        for name, aliases in [('Corte',['Corte','Cortado']),('Aparado',['Aparado']),('Conformado',['Conformado']),('Solado',['Solado']),('Terminado',['Terminado'])]:
            key = 'real-recipe-center:'+name
            center = migration._ref(key)
            if not center:
                center = self.env['mrp.workcenter'].search([
                    ('name','in',aliases+[v.upper() for v in aliases]+[v.lower() for v in aliases]),('company_id','=',self.company_id.id)],limit=1)
                if not center:
                    center = self.env['mrp.workcenter'].create({'name':name,'company_id':self.company_id.id})
                migration._bind(key,center)
            if center.company_id != self.company_id or not center.active:
                raise UserError(_('Revise el centro %s.',name))
            centers.append(center)
        results = self.env['mrp.bom']
        notes = []
        for template in self.template_ids:
            key = 'bom:'+next(r['key'] for r in data['finished'] if migration._ref(r['key']) == template)
            bom = migration._ref(key)
            if not bom:
                found = self.env['mrp.bom'].with_context(active_test=False).search([
                    ('product_tmpl_id','=',template.id),('company_id','=',self.company_id.id),
                    ('code','=',self.code)],limit=2)
                if found:
                    notes.append(template.display_name+': ya tiene una receta manual de este código; no se modificó.')
                    results |= found
                    continue
                bom = self.env['mrp.bom'].with_company(self.company_id).create({
                    'code':self.code,'product_tmpl_id':template.id,'company_id':self.company_id.id,
                    'type':'normal','product_qty':1,'uom_id':template.uom_id.id,
                    'esi_multi_variant':True,'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)],
                    'bom_line_ids':[(0,0,dict(v[2])) for v in values],
                    'esi_center_route_ids':[(0,0,{'sequence':10*(i+1),'workcenter_id':c.id,
                        'minutes_per_unit':self.minutes_per_pair}) for i,c in enumerate(centers)],
                })
                migration._bind(key,bom)
                notes.append(template.display_name+': creada con todas sus tallas y los cinco centros.')
            else:
                notes.append(template.display_name+': ya creada; no se duplicó ni se sobrescribieron sus componentes.')
            results |= bom
        self.result = '\n'.join(notes)
        migration.recipe_log = self.result
        return {'type':'ir.actions.act_window','name':_('Recetas de Fábrica'),
                'res_model':'mrp.bom','view_mode':'list,form','domain':[('id','in',results.ids)]}


class RealComponent(models.Model):
    _name = 'tosscano.recipe.component'
    _description = 'Correspondencia de componente de receta'
    _order = 'source_row,id'

    recipe_id = fields.Many2one('tosscano.recipe.config', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='recipe_id.company_id', store=True)
    source_row = fields.Integer(required=True, readonly=True)
    source_code = fields.Char(readonly=True, string='Código ficha')
    source_name = fields.Char(readonly=True, string='Material ficha')
    source_unit = fields.Char(readonly=True, string='Unidad ficha')
    source_qty = fields.Float(readonly=True, digits=(16,6), string='Cantidad ficha por par')
    product_id = fields.Many2one('product.product', string='Componente migrado')
    inventory_uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad inventario')
    inventory_qty_per_pair = fields.Float(digits=(16,6), string='Cantidad inventario por par')
    issue = fields.Char(readonly=True, string='Observación')

    @api.onchange('product_id')
    def _onchange_real_product(self):
        self.inventory_qty_per_pair = 0
        self.recipe_id.reviewed = False


class RealMigration(models.Model):
    _inherit = 'tosscano.migration'

    def action_prepare_real_recipes(self):
        self._lock()
        if not self.data_imported:
            raise UserError(_('Primero importe los datos.'))
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requieren permisos de administrador de Fabricación.'))
        self.action_archive_recipe_test_data()
        data = self._source()
        by_code = {}
        for row in data['materials']:
            product = self._ref(row['key'])
            if product:
                by_code.setdefault(row['code'],[]).append(product)
        configs = self.env['tosscano.recipe.config']
        for recipe in data['recipes']:
            key='real-recipe-config:'+recipe['code']
            config=self._ref(key)
            if not config:
                targets = [self._ref(r['key']).id for r in data['finished']
                    if r['code'].startswith(recipe['code']+'-') and self._ref(r['key'])]
                config=configs.create({'migration_id':self.id,'code':recipe['code'],'name':recipe['title'],
                                       'template_ids':[(6,0,targets)]})
                self._bind(key,config)
            existing_rows = set(config.line_ids.mapped('source_row'))
            for row in [r for r in data['components'] if r['recipe']==recipe['code'] and r['qty_per_pair']>0 and r['row'] not in existing_rows]:
                products=by_code.get(row['code'],[])
                product=products[0] if len(products)==1 else False
                quantity=0
                issue='Seleccione el material correspondiente del catálogo migrado.'
                if row['code']=='ACC-BOL-CEL-35':
                    # Source code reused for bag and numbering: never decide by code alone.
                    product=False
                    issue='El código de la ficha identifica bolsa y numeración; seleccione el material correcto.'
                if product:
                    uom=self._uom(row['uom'])
                    if uom == product.uom_id or uom._has_common_reference(product.uom_id):
                        quantity=uom._compute_quantity(row['qty_per_pair'],product.uom_id,round=False)
                        issue='Coincidencia por código y unidad; revise aplicación por talla/color.'
                    else:
                        issue='Confirme la cantidad equivalente por par en la unidad de inventario; no se asumió conversión.'
                self.env['tosscano.recipe.component'].create({
                    'recipe_id':config.id,'source_row':row['row'],'source_code':row['code'],
                    'source_name':row['name'],'source_unit':row['uom'],'source_qty':row['qty_per_pair'],
                    'product_id':product.id if product else False,'inventory_qty_per_pair':quantity,'issue':issue})
            configs |= config
        self.recipe_log='Correspondencias preparadas. Las recetas se crearán con los productos y componentes migrados, todas sus tallas y cinco centros. No se crean materiales separados.'
        return {'type':'ir.actions.act_window','name':_('Recetas de Fábrica'),
                'res_model':'tosscano.recipe.config','view_mode':'list,form',
                'domain':[('migration_id','=',self.id)]}

    def action_archive_recipe_test_data(self):
        self._lock()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requieren permisos de administrador de Fabricación.'))
        notes=[]
        data=self._source()
        for recipe in data['recipes']:
            bom=self._ref('recipe-demo-bom:'+recipe['code'])
            template=self._ref('recipe-demo-template:'+recipe['code'])
            if bom and self.env['mrp.production'].search_count([('bom_id','=',bom.id)]):
                notes.append(recipe['code']+': conserva receta de prueba, referenciada por una OF.')
                continue
            if bom:
                bom.active=False
            if template:
                products=template.with_context(active_test=False).product_variant_ids
                has_history=self.env['stock.move'].search_count([('product_id','in',products.ids)])
                has_stock=self.env['stock.quant'].search_count([('product_id','in',products.ids),'|',('quantity','!=',0),('reserved_quantity','!=',0)])
                if not has_history and not has_stock:
                    template.active=False
            notes.append(recipe['code']+': receta auxiliar archivada si existía; no se borraron movimientos.')
        # Auxiliary materials are preserved: another BOM or inventory document may use them.
        self.recipe_log='\n'.join(notes)+'\nLos materiales auxiliares se conservan para no afectar documentos existentes.'
        return True
