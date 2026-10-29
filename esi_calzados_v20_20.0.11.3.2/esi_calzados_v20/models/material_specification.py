from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    esi_material_type = fields.Char(
        string='Tipo', index=True,
        help='Clasificación descriptiva del catálogo: LISO, METAL, CINTA, etc. No cambia el tipo de producto de Odoo.')
    esi_measure = fields.Char(
        string='Medida',
        help='Especificación descriptiva como 2.5CM, 35X50 o #40. No sustituye la unidad de medida ni las variantes por talla. Se comparte entre las variantes de esta plantilla.')
