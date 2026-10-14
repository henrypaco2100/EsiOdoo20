import math
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from .batch_math import cost_shares


class ProductionGroup(models.Model):
    _inherit = 'esi.production.group'
    _check_company_auto = True

    mode = fields.Selection([('variants', 'Una OF por variante'), ('multi', 'Una OF con varias tallas')],
                            default='variants', required=True, string='Fabricación')
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

    def _batch_recipe(self):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Crear la receta multitalla requiere el rol Responsable de Fabricación.'))
        if not self.env.user.has_group('mrp.group_mrp_byproducts'):
            raise UserError(_('Active Subproductos en Fabricación > Configuración > Ajustes para registrar las cantidades de cada talla.'))
        products = self.line_ids.product_id
        if len(products) < 2 or len(products) != len(self.line_ids):
            raise UserError(_('Use al menos dos variantes distintas, sin repetir productos.'))
        if len(products.product_tmpl_id) != 1:
            raise UserError(_('La OF multitalla requiere variantes del mismo producto.'))
        if any(not p.is_storable for p in products):
            raise UserError(_('Las salidas deben ser productos con seguimiento de inventario.'))
        ordered = self.line_ids.sorted(lambda l: (-l.quantity, l.id))
        primary = ordered[0]
        boms = self.env['mrp.bom']
        for line in ordered:
            bom = line.bom_id or self.env['mrp.bom']._bom_find(line.product_id, company_id=self.company_id.id, bom_type='normal').get(line.product_id)
            if not bom:
                raise UserError(_('Falta la lista de materiales de %s.') % line.product_id.display_name)
            boms |= bom
        if len(boms) != 1:
            raise UserError(_('Todas las tallas deben compartir la misma lista de materiales. Use OF por variante si sus recetas difieren.'))
        bom = boms
        if bom.type != 'normal' or bom.product_id or bom.product_tmpl_id != primary.product_id.product_tmpl_id:
            raise UserError(_('Seleccione una lista de materiales normal, común a todas las variantes.'))
        if bom.company_id and bom.company_id != self.company_id:
            raise UserError(_('La lista de materiales pertenece a otra compañía.'))
        if bom.operation_ids or bom.byproduct_ids or bom.bom_line_ids.bom_product_template_attribute_value_ids:
            raise UserError(_('Esta modalidad admite una receta común sin operaciones de centro de trabajo, subproductos previos ni componentes condicionados por variante. Para esas recetas use OF por variante.'))
        if not bom.bom_line_ids or bom.product_qty <= 0:
            raise UserError(_('La receta debe tener componentes y cantidad base positiva.'))
        if self.env['mrp.bom']._bom_find(bom.bom_line_ids.product_id, company_id=self.company_id.id, bom_type='phantom'):
            raise UserError(_('Las recetas con kits anidados deben procesarse por variante.'))
        quantities = [line.uom_id._compute_quantity(line.quantity, primary.uom_id, round=False) for line in ordered]
        try:
            shares = cost_shares(quantities)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        total_bom_units = primary.uom_id._compute_quantity(sum(quantities), bom.uom_id, round=False)
        factor = total_bom_units / bom.product_qty
        components = [Command.create({'product_id': line.product_id.id,
            'product_qty': line.product_qty * factor, 'uom_id': line.uom_id.id,
            'sequence': line.sequence}) for line in bom.bom_line_ids]
        outputs = [Command.create({'product_id': line.product_id.id, 'product_qty': line.quantity,
            'uom_id': line.uom_id.id, 'cost_share': shares[i]}) for i, line in enumerate(ordered) if i]
        # Archived from inception: this dedicated recipe must never replace a normal product BoM.
        batch_bom = bom.copy({'active': False, 'company_id': self.company_id.id,
            'code': self.name, 'product_id': primary.product_id.id,
            'picking_type_id': self.picking_type_id.id, 'enable_batch_size': False,
            'product_qty': primary.quantity, 'uom_id': primary.uom_id.id,
            'bom_line_ids': [Command.clear()] + components,
            'byproduct_ids': [Command.clear()] + outputs})
        return primary, batch_bom

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
            primary, bom = scoped._batch_recipe()
            production = self.env['mrp.production'].with_company(group.company_id).create({
                'company_id': group.company_id.id, 'product_id': primary.product_id.id,
                'product_qty': primary.quantity, 'uom_id': primary.uom_id.id, 'bom_id': bom.id,
                'picking_type_id': group.picking_type_id.id, 'origin': group.name,
                'esi_group_id': group.id, 'esi_responsible_id': group.responsible_id.id,
                'esi_analytic_account_id': group.analytic_account_id.id})
            production.action_confirm()
            group.write({'batch_bom_id': bom.id, 'state': 'created'})
        return True

    def action_cancel(self):
        if any(g.state != 'draft' or g.production_ids for g in self):
            raise UserError(_('Cancele las órdenes mediante el flujo nativo. Solo se cancelan aquí grupos borrador sin órdenes.'))
        return super().action_cancel()


class GroupLine(models.Model):
    _inherit = 'esi.production.group.line'
    company_id = fields.Many2one(related='group_id.company_id', store=True)
    variant_label = fields.Char(related='product_id.esi_variant_highlight', string='Talla / atributos')

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
