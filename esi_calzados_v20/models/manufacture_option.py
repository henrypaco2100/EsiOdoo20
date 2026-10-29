from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    esi_manufacture_ok = fields.Boolean(
        string='Fabricar', default=False, index=True,
        help='Permite seleccionar este producto y sus variantes como producto a fabricar '
             'en listas de materiales, grupos y órdenes de fabricación. '
             'Puede activar también Componentes para productos semielaborados.')


class Bom(models.Model):
    _inherit = 'mrp.bom'

    product_tmpl_id = fields.Many2one(
        domain="[('type', '=', 'consu'), ('esi_manufacture_ok', '=', True)]")
    product_id = fields.Many2one(
        domain="[('product_tmpl_id', '=', product_tmpl_id), ('type', '=', 'consu'), ('esi_manufacture_ok', '=', True)]")


class Production(models.Model):
    _inherit = 'mrp.production'

    product_id = fields.Many2one(
        domain="[('is_storable', '=', True), ('esi_manufacture_ok', '=', True)]")


class OutputLine(models.Model):
    _inherit = 'esi.production.output.line'

    product_id = fields.Many2one(domain="[('esi_manufacture_ok', '=', True)]")

