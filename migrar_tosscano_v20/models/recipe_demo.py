import hashlib
import math
from odoo import models, _
from odoo.exceptions import UserError


def recipe_unit(label):
    normalized = str(label or '').strip().upper()
    return {'UNI':'UNIDAD','UN':'UNIDAD','L':'LITRO','GR':'GRAMO','G':'GRAMO',
            'M':'METRO','M2':'M2','FT2':'PIE2','PAR':'PAR','KG':'KG'}.get(normalized, normalized)


def demo_material_key(row):
    # Same source code can describe different materials, or incompatible prices.
    identity = (row.get('code') or '', row['name'].strip().casefold(),
                recipe_unit(row['uom']), str(row['unit_price']))
    return 'recipe-demo-material:' + hashlib.sha256(repr(identity).encode()).hexdigest()


class RecipeDemo(models.Model):
    _inherit = 'tosscano.migration'

    def action_create_demo_recipes(self):
        self._lock()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Se requieren permisos de administrador de Fabricación.'))
        if not self.data_imported:
            raise UserError(_('Primero importe los datos.'))
        if 'esi_center_route_ids' not in self.env['mrp.bom']._fields:
            raise UserError(_('Actualice ESI Calzados: falta Recorrido por centros.'))
        data = self._source()
        for row in data['components']:
            if not math.isfinite(row['qty_per_pair']) or row['qty_per_pair'] < 0:
                raise UserError(_('Cantidad inválida en la ficha %s.', row['recipe']))
            if row['qty_per_pair'] > 0 and (not row['name'] or not recipe_unit(row['uom']) or not isinstance(row['unit_price'],(int,float)) or not math.isfinite(row['unit_price']) or row['unit_price'] < 0):
                raise UserError(_('Revise nombre, unidad y precio en la ficha %s, fila %s.', row['recipe'], row['row']))
        company = self.factory_id
        model = self.env['product.template'].with_company(company)
        component_category = self._category('Recetas de demostración', 'Materiales de ficha', 'Materia prima')
        component_category.write({'property_cost_method': 'average'})
        finished_category = self._category('Recetas de demostración', 'Calzados de prueba', 'Producto terminado')
        finished_category.write({'property_cost_method': 'average'})
        centers = []
        for name in ['Corte','Aparado','Conformado','Solado','Terminado']:
            key = 'recipe-demo-center:' + name
            center = self._ref(key)
            if not center:
                center = self.env['mrp.workcenter'].search([
                    ('name','=ilike',name), ('company_id','=',company.id)],limit=1)
                if not center:
                    center = self.env['mrp.workcenter'].create({'name':name,'company_id':company.id})
                self._bind(key, center)
            if center.company_id != company or not center.active:
                raise UserError(_('Revise la compañía y estado del centro %s.',name))
            centers.append(center)
        created = 0
        notes = ['RECETAS DE DEMOSTRACIÓN EN FÁBRICA',
                 'Productos y materiales DEMO separados del inventario real, sin cargar existencias.']
        for recipe in data['recipes']:
            code = recipe['code']
            key = 'recipe-demo-template:' + code
            template = self._ref(key)
            if not template:
                template = model.create({
                    'name':'DEMO | '+recipe['title'].split('·')[-1].strip(),
                    'company_id':company.id, 'type':'consu','is_storable':True,
                    'categ_id':finished_category.id,'uom_id':self._uom('PAR').id,
                    'sale_ok':True,'purchase_ok':False,'esi_manufacture_ok':True,
                    'esi_component_ok':False,'product_add_mode':'matrix',
                    'attribute_line_ids':[self._attribute_line('Talla',list(range(34,47)),True)],
                })
                for variant in template.product_variant_ids:
                    size = variant.product_template_attribute_value_ids.filtered(lambda v:v.attribute_id.name=='Talla').name
                    variant.default_code = 'DEMO-'+code+'-T'+size
                self._bind(key,template)
            bom_key = 'recipe-demo-bom:' + code
            bom = self._ref(bom_key)
            if bom:
                if bom.company_id != company or bom.product_tmpl_id != template:
                    raise UserError(_('La receta de prueba %s fue reasignada. Revísela.',code))
                bom.write({'esi_multi_variant':True,
                           'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)]})
                notes.append(code+': receta existente; tallas sincronizadas, componentes y recorrido conservados.')
                continue
            lines = []
            for row in [r for r in data['components'] if r['recipe']==code and r['qty_per_pair']>0]:
                material_key = demo_material_key(row)
                product = self._ref(material_key)
                uom = self._uom(recipe_unit(row['uom']))
                if not product:
                    material = model.create({
                        'name':'DEMO | '+row['name'], 'company_id':company.id,
                        'default_code':'DEMO-MAT-'+material_key.split(':')[-1][:16],
                        'type':'consu','is_storable':True,'uom_id':uom.id,
                        'categ_id':component_category.id,'esi_component_ok':True,
                        'esi_manufacture_ok':False,'sale_ok':False,'purchase_ok':True,
                    })
                    product = material.product_variant_id
                    product.with_company(company).standard_price = row['unit_price']
                    self._bind(material_key,product)
                if product.uom_id != uom or product.company_id != company:
                    raise UserError(_('Se modificó la unidad o compañía del material DEMO %s.', product.display_name))
                lines.append((0,0,{'product_id':product.id,'product_qty':row['qty_per_pair'],'uom_id':uom.id}))
            if not lines:
                raise UserError(_('La ficha %s no tiene componentes positivos.',code))
            bom = self.env['mrp.bom'].with_company(company).create({
                'product_tmpl_id':template.id,'company_id':company.id,'code':'DEMO-'+code,
                'type':'normal','product_qty':1,'uom_id':self._uom('PAR').id,
                'esi_multi_variant':True,'esi_allowed_variant_ids':[(6,0,template.product_variant_ids.ids)],
                'bom_line_ids':lines,
                'esi_center_route_ids':[(0,0,{'sequence':(i+1)*10,'workcenter_id':center.id,
                                            'minutes_per_unit':1}) for i,center in enumerate(centers)],
            })
            self._bind(bom_key,bom)
            created += 1
            notes.append(code+': receta creada, tallas 34–46 seleccionadas y cinco centros asignados.')
        notes.append('%s recetas nuevas. Tiempos provisionales: 1 minuto por par en cada centro, solo para probar el recorrido; no son tiempos medidos ni costos de mano de obra de la ficha.'%created)
        self.recipe_log = '\n'.join(notes)
        self.import_log = (self.import_log or '')+'\n\n'+self.recipe_log
        return {'type':'ir.actions.act_window','name':_('Recetas de demostración'),
                'res_model':'mrp.bom','view_mode':'list,form',
                'domain':[('company_id','=',company.id),('id','in',[self._ref('recipe-demo-bom:'+r['code']).id for r in data['recipes']])]}
