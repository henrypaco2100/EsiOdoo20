from odoo import api, fields, models


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'
    esi_highlight_card = fields.Boolean(string='Destacar en tarjeta del producto',
        help='Muestra el nombre y valor del atributo en letra grande debajo del producto. Por ejemplo: Talla: 40.')


class Product(models.Model):
    _inherit = 'product.product'
    esi_variant_highlight = fields.Char(compute='_compute_esi_variant_highlight', string='Variantes destacadas')

    @api.depends('product_template_attribute_value_ids',
                 'product_template_attribute_value_ids.name',
                 'product_template_attribute_value_ids.attribute_id.name',
                 'product_template_attribute_value_ids.attribute_id.esi_highlight_card')
    def _compute_esi_variant_highlight(self):
        for product in self:
            values = product.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id.esi_highlight_card)
            product.esi_variant_highlight = ' · '.join('%s: %s' % (v.attribute_id.name, v.name) for v in values)


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    esi_variant_highlight = fields.Char(compute='_compute_esi_variant_highlight', string='Variantes disponibles')

    @api.depends('attribute_line_ids.value_ids', 'attribute_line_ids.value_ids.name',
                 'attribute_line_ids.attribute_id.name', 'attribute_line_ids.attribute_id.esi_highlight_card')
    def _compute_esi_variant_highlight(self):
        for product in self:
            lines = product.attribute_line_ids.filtered(lambda l: l.attribute_id.esi_highlight_card)
            product.esi_variant_highlight = ' · '.join('%s: %s' % (l.attribute_id.name, ' / '.join(l.value_ids.mapped('name'))) for l in lines)
