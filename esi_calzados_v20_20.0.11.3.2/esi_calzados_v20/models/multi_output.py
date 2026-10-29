import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from .batch_math import cost_shares
from .grouping_math import production_key


class ProductionGroup(models.Model):
    _inherit = 'esi.production.group'
    _check_company_auto = True

    mode = fields.Selection([('variants', 'Una OF por variante'), ('multi', 'Agrupar tallas; separar los demás atributos')],
                            default='multi', required=True, string='Fabricación')
    sale_id = fields.Many2one('sale.order', string='Cotización origen', check_company=True, readonly=True, copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', string='Operación de fabricación', check_company=True,
        domain="[('code', '=', 'mrp_operation'), ('company_id', '=', company_id)]")
    batch_bom_id = fields.Many2one('mrp.bom', string='Receta del lote', readonly=True, copy=False, check_company=True)

    @api.onchange('company_id')
    def _onchange_batch_company(self):
        self.picking_type_id = False

    def write(self, values):
        protected = {'line_ids', 'company_id', 'mode', 'picking_type_id'}
        if protected.intersection(values) and any(g.state != 'draft' or g.production_ids for g in self):
            raise UserError(_('No se puede cambiar la receta de un grupo con órdenes creadas.'))
        return super().write(values)

    def _production_buckets(self):
        self.ensure_one()
        buckets = {}
        for line in self.line_ids:
            p = line.product_id
            values = p.product_template_attribute_value_ids
            grouped = values.attribute_id.filtered('esi_group_production')
            key = production_key(p.product_tmpl_id.id,
                [(v.attribute_id.id, v.id) for v in values], grouped.ids, p.id)
            buckets[key] = buckets.get(key, self.env['esi.production.group.line']) | line
        return list(buckets.values())

    def _batch_recipe(self, lines, primary_product=None):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Crear una receta agrupada requiere Responsable de Fabricación.'))
        if not self.env.user.has_group('mrp.group_mrp_byproducts'):
            raise UserError(_('Active Subproductos en Fabricación > Configuración > Ajustes para las salidas por talla.'))
        quantities = {}
        for line in lines:
            quantities[line.product_id] = quantities.get(line.product_id, 0.0) + line.quantity
        ordered = sorted(quantities, key=lambda p: (-quantities[p], p.id))
        if primary_product:
            if primary_product not in quantities:
                raise UserError(_('Introduzca una cantidad para la variante de referencia.'))
            ordered.remove(primary_product)
            ordered.insert(0, primary_product)
        primary = ordered[0]
        boms = self.env['mrp.bom']
        for line in lines:
            bom = line.bom_id or self.env['mrp.bom']._bom_find(line.product_id,
                company_id=self.company_id.id, bom_type='normal').get(line.product_id)
            if not bom:
                raise UserError(_('Falta la lista de materiales de %s.') % line.product_id.display_name)
            boms |= bom
        if len(boms) != 1:
            raise UserError(_('Las tallas de una combinación deben compartir una receta de plantilla. Revise las recetas seleccionadas.'))
        bom = boms
        bom._esi_check_allowed_products(lines.product_id)
        if bom.type != 'normal' or bom.product_id or bom.product_tmpl_id != primary.product_tmpl_id:
            raise UserError(_('La fabricación agrupada necesita una receta normal de plantilla, sin variante exclusiva.'))
        if bom.company_id and bom.company_id != self.company_id:
            raise UserError(_('La receta pertenece a otra compañía.'))
        if bom.byproduct_ids:
            raise UserError(_('La receta ya tiene subproductos. Use OF por variante para conservar su reparto de costos.'))
        if bom.operation_ids.bom_product_template_attribute_value_ids:
            raise UserError(_('Las operaciones condicionadas por variante necesitan una ruta común antes de agrupar. Los materiales sí pueden estar condicionados.'))
        if not bom.bom_line_ids or bom.product_qty <= 0:
            raise UserError(_('La receta debe tener componentes y cantidad base positiva.'))
        if any(not p.is_storable for p in ordered):
            raise UserError(_('Las salidas deben controlar existencias.'))
        if self.env['mrp.bom']._bom_find(bom.bom_line_ids.product_id,
                company_id=self.company_id.id, bom_type='phantom'):
            raise UserError(_('Las recetas con kits anidados deben procesarse por variante.'))
        amounts = [p.uom_id._compute_quantity(quantities[p], primary.uom_id, round=False) for p in ordered]
        try:
            shares = cost_shares(amounts)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        # Evaluate each variant's conditions BEFORE aggregation. Size-specific soles
        # remain distinct, while common leather/thread quantities are added together.
        components = {}
        for product in ordered:
            factor = product.uom_id._compute_quantity(quantities[product], bom.uom_id, round=False) / bom.product_qty
            for line in bom.bom_line_ids:
                if line._skip_bom_line(product):
                    continue
                key = (line.product_id.id, line.uom_id.id, line.operation_id.id)
                if key not in components:
                    components[key] = {'product_id': line.product_id.id, 'uom_id': line.uom_id.id,
                        'operation_id': line.operation_id.id, 'product_qty': 0.0, 'sequence': line.sequence}
                components[key]['product_qty'] += line.product_qty * factor
        if not components:
            raise UserError(_('Ningún componente de la receta aplica a estas variantes.'))
        outputs = [Command.create({'product_id': p.id, 'product_qty': quantities[p],
            'uom_id': p.uom_id.id, 'cost_share': shares[i]}) for i, p in enumerate(ordered) if i]
        # Native copy remaps operation IDs and dependency links onto the copied BoM.
        # Keep the original BoM base capacity for work order duration calculations.
        batch_bom = bom.copy({'esi_batch_snapshot': True, 'esi_total_basis': True, 'esi_multi_variant': False, 'esi_allowed_variant_ids': [Command.clear()], 'active': False, 'company_id': self.company_id.id,
            'code': self.name, 'product_id': primary.id,
            'picking_type_id': self.picking_type_id.id, 'enable_batch_size': False,
            'product_qty': sum(amounts), 'uom_id': primary.uom_id.id,
            'bom_line_ids': [Command.create(v) for v in components.values()], 'byproduct_ids': outputs})
        for original, copied in zip(bom.operation_ids, batch_bom.operation_ids.sorted()):
            copied.write({'time_mode': 'manual', 'time_cycle_manual': original.time_cycle})
        return primary, sum(amounts), batch_bom, bom

    def action_create_productions(self):
        for group in self:
            group.check_access('write')
            # Serialize concurrent button calls; no privilege changes or business-data SQL writes.
            self.env.cr.execute('SELECT id FROM esi_production_group WHERE id = %s FOR UPDATE', [group.id])
            group.invalidate_recordset(['state', 'production_ids'])
            if group.state != 'draft':
                continue
            if group.company_id not in self.env.companies:
                raise UserError(_('Active la sucursal del grupo antes de fabricar.'))
            if not group.responsible_id or not group.line_ids:
                raise UserError(_('Indique encargado y productos.'))
            if not group.picking_type_id or group.picking_type_id.company_id != group.company_id or group.picking_type_id.code != 'mrp_operation':
                raise UserError(_('Seleccione la operación de fabricación de esta sucursal.'))
            if group.sale_id:
                group.sale_id._esi_check_manual_group_routes()
                if self.env['mrp.production'].search_count([('company_id', '=', group.company_id.id), ('origin', '=', group.sale_id.name), ('state', '!=', 'cancel')]):
                    raise UserError(_('La venta ya tiene fabricación automática. Revísela antes de crear otra.'))
            group.line_ids._check_batch_lines()
            scoped = group.with_company(group.company_id).with_context(default_picking_type_id=group.picking_type_id.id)
            if group.mode == 'variants':
                super(ProductionGroup, scoped).action_create_productions()
                continue
            batches = self.env['mrp.bom']
            for lines in scoped._production_buckets():
                products = lines.product_id
                if len(products) == 1:
                    product = products
                    boms = lines.bom_id
                    if len(boms) > 1:
                        raise UserError(_('Un mismo producto tiene recetas distintas en el grupo.'))
                    bom = boms or self.env['mrp.bom']._bom_find(product,
                        company_id=group.company_id.id, bom_type='normal').get(product)
                    if not bom:
                        raise UserError(_('Falta la receta de %s.') % product.display_name)
                    quantity = sum(lines.mapped('quantity'))
                    source = bom
                    batch = False
                else:
                    product, quantity, bom, source = scoped._batch_recipe(lines)
                    batches |= bom
                    batch = True
                production = self.env['mrp.production'].with_company(group.company_id).create({
                    'company_id': group.company_id.id, 'product_id': product.id,
                    'product_qty': quantity, 'uom_id': product.uom_id.id, 'bom_id': bom.id,
                    'picking_type_id': group.picking_type_id.id, 'origin': group.name,
                    'esi_group_id': group.id, 'esi_responsible_id': group.responsible_id.id,
                    'esi_analytic_account_id': group.analytic_account_id.id,
                    'esi_size_batch': batch, 'esi_source_bom_id': source.id,
                    'esi_source_base_qty': source.uom_id._compute_quantity(source.product_qty, product.uom_id, round=False),
                    'esi_batch_attribute_ids': [Command.set(product.product_template_attribute_value_ids.attribute_id.filtered('esi_group_production').ids)]})
                production.action_confirm()
            group.write({'batch_bom_id': batches[:1].id, 'state': 'created'})
        return True

    def action_cancel(self):
        if any(g.state != 'draft' or g.production_ids for g in self):
            raise UserError(_('Cancele las órdenes mediante el flujo nativo. Solo se cancelan aquí grupos borrador sin órdenes.'))
        return super().action_cancel()


class GroupLine(models.Model):
    _inherit = 'esi.production.group.line'
    company_id = fields.Many2one(related='group_id.company_id', store=True)
    variant_label = fields.Char(related='product_id.display_name', string='Variantes')

    @api.constrains('product_id', 'quantity', 'bom_id', 'group_id')
    def _check_batch_lines(self):
        for line in self:
            if not math.isfinite(line.quantity) or line.quantity <= 0 or not line.product_id or line.uom_id.is_zero(line.quantity):
                raise ValidationError(_('Seleccione producto y cantidad mayor que cero.'))
            if line.product_id.company_id and line.product_id.company_id != line.company_id:
                raise ValidationError(_('El producto pertenece a otra compañía.'))
            bom = line.bom_id
            if bom and (bom.type != 'normal' or bom.product_tmpl_id != line.product_tmpl_id or
                        (bom.product_id and bom.product_id != line.product_id) or
                        (bom.company_id and bom.company_id != line.company_id)):
                raise ValidationError(_('La receta no corresponde a la variante o compañía.'))

    @api.onchange('product_id')
    def _onchange_batch_product(self):
        self.bom_id = False

    @api.model_create_multi
    def create(self, vals_list):
        groups = self.env['esi.production.group'].browse([v['group_id'] for v in vals_list if v.get('group_id')])
        if any(g.state != 'draft' or g.production_ids for g in groups):
            raise UserError(_('No agregue productos después de crear las órdenes.'))
        return super().create(vals_list)

    def write(self, vals):
        targets = self.group_id | self.env['esi.production.group'].browse(vals.get('group_id', []))
        if any(g.state != 'draft' or g.production_ids for g in targets):
            raise UserError(_('Las líneas de un grupo fabricado no se pueden modificar.'))
        return super().write(vals)

    def unlink(self):
        if any(g.state != 'draft' or g.production_ids for g in self.group_id):
            raise UserError(_('No elimine líneas con órdenes creadas.'))
        return super().unlink()
