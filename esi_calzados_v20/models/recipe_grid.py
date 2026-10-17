from odoo import models, _
from odoo.exceptions import UserError


class Template(models.Model):
    _inherit = 'product.template'

    def esi_get_recipe_selection_grid(self, selected_ids=None):
        self.ensure_one()
        self.check_access('read')
        if not self.attribute_line_ids.attribute_id.filtered('esi_group_production'):
            raise UserError(_('Marque «Compartir materiales entre sus valores» en el atributo Talla antes de seleccionar la receta compartida.'))
        grid = self.esi_get_production_matrix()
        products = {tuple(sorted(p.product_template_attribute_value_ids.ids)): p
            for p in self.product_variant_ids if p.is_storable}
        selected = set(selected_ids or [])
        available = False
        for row in grid['matrix']:
            for cell in row[1:]:
                product = products.get(tuple(cell.get('ptav_ids', [])))
                cell['product_id'] = product.id if product else False
                cell['is_possible_combination'] = bool(product and cell.get('is_possible_combination'))
                cell['qty'] = int(bool(product and product.id in selected))
                available |= cell['is_possible_combination']
        if not available:
            raise UserError(_('La plantilla no tiene variantes almacenables disponibles.'))
        return grid
