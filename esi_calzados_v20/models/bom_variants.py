from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import ValidationError, AccessError
from .grouping_math import production_key


class Bom(models.Model):
    _inherit = 'mrp.bom'

    esi_multi_variant = fields.Boolean(string='Receta compartida entre tallas',
        help='Seleccione las variantes terminadas que pueden utilizar esta receta. Solo pueden variar los atributos marcados para compartir materiales.')
    esi_allowed_variant_ids = fields.Many2many('product.product',
        'esi_bom_allowed_variant_rel', 'bom_id', 'product_id',
        string='Variantes permitidas', check_company=True)

    @api.onchange('esi_multi_variant')
    def _onchange_shared_recipe(self):
        if self.esi_multi_variant:
            if self.product_id:
                self.esi_allowed_variant_ids = self.product_id
            self.product_id = False

    @api.onchange('product_tmpl_id')
    def _onchange_shared_template(self):
        self.esi_allowed_variant_ids = self.esi_allowed_variant_ids.filtered(
            lambda p: p.product_tmpl_id == self.product_tmpl_id)

    @api.constrains('esi_multi_variant', 'esi_allowed_variant_ids', 'product_tmpl_id', 'product_id', 'type', 'company_id')
    def _check_shared_variants(self):
        for bom in self.filtered('esi_multi_variant'):
            products = bom.esi_allowed_variant_ids
            if bom.type != 'normal' or bom.product_id or not products:
                raise ValidationError(_('Una receta compartida debe ser de fabricación, sin variante exclusiva y con variantes permitidas.'))
            grouped = bom.product_tmpl_id.attribute_line_ids.attribute_id.filtered('esi_group_production')
            if not grouped:
                raise ValidationError(_('Marque «Compartir materiales entre sus valores» en el atributo Talla.'))
            keys = set()
            for product in products:
                if product.product_tmpl_id != bom.product_tmpl_id or not product.is_storable:
                    raise ValidationError(_('Todas las variantes deben pertenecer a la plantilla y controlar existencias.'))
                if product.company_id and product.company_id != bom.company_id:
                    raise ValidationError(_('La variante y la receta deben pertenecer a la misma compañía.'))
                keys.add(production_key(bom.product_tmpl_id.id,
                    [(v.attribute_id.id, v.id) for v in product.product_template_attribute_value_ids], grouped.ids, product.id))
            if len(keys) != 1:
                raise ValidationError(_('Las variantes de esta receta deben compartir color, modelo y material. Solo pueden diferir en los atributos marcados, como Talla.'))

    def _esi_check_allowed_products(self, products):
        self.ensure_one()
        if self.esi_multi_variant and products - self.esi_allowed_variant_ids:
            raise ValidationError(_('Hay productos que no están entre las variantes permitidas de la receta.'))

    @api.model
    def _bom_find_domain(self, products, picking_type=None, company_id=False, bom_type=False):
        domain = super()._bom_find_domain(products, picking_type, company_id, bom_type)
        if len(products) == 1:
            domain &= Domain('esi_multi_variant', '=', False) | Domain('esi_allowed_variant_ids', 'in', products.ids)
        return domain

    @api.model
    def _bom_find(self, products, picking_type=None, company_id=False, bom_type=False):
        result = super()._bom_find(products, picking_type, company_id, bom_type)
        # Native multi-product lookup caches generic recipes by template. Resolve
        # restricted templates individually so the allowed list remains effective.
        if len(products) <= 1:
            return result
        try:
            restricted = self.search([('esi_multi_variant', '=', True),
                ('product_tmpl_id', 'in', products.product_tmpl_id.ids)]).product_tmpl_id
        except AccessError:
            return result
        for product in products.filtered(lambda p: p.product_tmpl_id in restricted and p.type != 'service'):
            match = super()._bom_find(product, picking_type, company_id, bom_type).get(product)
            result.pop(product, None)
            if match:
                result[product] = match
        return result

    def explode(self, product, quantity, picking_type=False, never_attribute_values=False):
        # Native MRP also calls explode on an empty BoM during form onchange.
        # Preserve that behavior; validate allowed variants only for a real BoM.
        if self and product:
            self._esi_check_allowed_products(product)
        return super().explode(product, quantity, picking_type, never_attribute_values)


class Production(models.Model):
    _inherit = 'mrp.production'

    @api.depends('product_id', 'never_product_template_attribute_value_ids')
    def _compute_bom_id(self):
        # Native MRP keeps a generic recipe when only the variant changes.
        # Shared recipes are generic too, but have a restricted variant list.
        # Let native lookup select a valid recipe using our existing domain.
        for mo in self:
            if (mo.state == 'draft' and mo.bom_id.esi_multi_variant
                    and mo.product_id not in mo.bom_id.esi_allowed_variant_ids):
                mo.bom_id = False
        return super()._compute_bom_id()

    @api.constrains('bom_id', 'product_id')
    def _check_allowed_bom_variant(self):
        for mo in self.filtered('bom_id'):
            mo.bom_id._esi_check_allowed_products(mo.product_id)
