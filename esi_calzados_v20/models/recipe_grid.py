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

        # First resolve the real product behind every matrix cell.
        for row in grid['matrix']:
            for cell in row[1:]:
                product = products.get(tuple(cell.get('ptav_ids', [])))
                cell['product_id'] = product.id if product else False
                cell['is_possible_combination'] = bool(product and cell.get('is_possible_combination'))
                available |= cell['is_possible_combination']

        if not available:
            raise UserError(_('La plantilla no tiene variantes almacenables disponibles.'))

        # New shared recipe: select every size from the first valid row by default.
        # A row fixes model/color/material; columns are the grouped attribute (Talla).
        # Existing recipes keep their current explicit selection.
        if not selected:
            for row in grid['matrix']:
                row_products = [cell.get('product_id') for cell in row[1:]
                                if cell.get('is_possible_combination') and cell.get('product_id')]
                if row_products:
                    selected.update(row_products)
                    break

        for row in grid['matrix']:
            for cell in row[1:]:
                cell['qty'] = int(bool(cell.get('product_id') and cell['product_id'] in selected))
        return grid
