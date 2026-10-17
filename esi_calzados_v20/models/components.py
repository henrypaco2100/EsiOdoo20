from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    esi_component_ok = fields.Boolean(string='Componentes', default=False, index=True,
        help='Permite usar este producto y sus variantes como componentes de recetas y órdenes de fabricación.')


class BomLine(models.Model):
    _inherit = 'mrp.bom.line'
    product_id = fields.Many2one(domain="[('type', 'in', ['consu', 'service']), ('esi_component_ok', '=', True)]")

    @api.constrains('product_id', 'bom_id')
    def _check_component_enabled(self):
        for line in self:
            if line.product_id and not line.product_id.esi_component_ok:
                raise ValidationError(_('Active «Componentes» en el producto %s antes de usarlo en una receta.') % line.product_id.display_name)


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.constrains('product_id', 'raw_material_production_id')
    def _check_manufacturing_component(self):
        for move in self:
            if move.raw_material_production_id and not move.product_id.esi_component_ok:
                raise ValidationError(_('Active «Componentes» en el producto %s antes de usarlo en fabricación.') % move.product_id.display_name)


class Bom(models.Model):
    _inherit = 'mrp.bom'

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        if self.env.context.get('child_field') == 'bom_line_ids':
            domain &= Domain('esi_component_ok', '=', True)
        return domain


class Production(models.Model):
    _inherit = 'mrp.production'

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        if self.env.context.get('child_field') == 'move_raw_ids':
            domain &= Domain('esi_component_ok', '=', True)
        return domain

    def action_confirm(self):
        for mo in self.filtered(lambda m: m.state == 'draft'):
            invalid = mo.move_raw_ids.product_id.filtered(lambda p: not p.esi_component_ok)
            if invalid:
                raise ValidationError(_('Active «Componentes» en estos productos antes de confirmar: %s') % ', '.join(invalid.mapped('display_name')))
        return super().action_confirm()


class Workorder(models.Model):
    _inherit = 'mrp.workorder'

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        if self.env.context.get('child_field') == 'move_raw_ids':
            domain &= Domain('esi_component_ok', '=', True)
        return domain
