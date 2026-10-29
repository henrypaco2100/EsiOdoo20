from odoo import api, fields, models


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_main_product_display = fields.Char(
        string='Producto principal', compute='_compute_esi_batch_display')
    esi_size_quantities_display = fields.Char(
        string='Tallas / cantidades', compute='_compute_esi_batch_display')

    def _esi_attribute_value(self, product, attribute_name):
        target = (attribute_name or '').strip().casefold()
        values = product.product_template_attribute_value_ids.filtered(
            lambda value: (value.attribute_id.name or '').strip().casefold() == target
        )
        return values[:1].name if values else False

    @staticmethod
    def _esi_size_sort_key(value):
        text = str(value or '').strip()
        try:
            return (0, float(text.replace(',', '.')), text)
        except ValueError:
            return (1, 0.0, text.casefold())

    @staticmethod
    def _esi_qty_text(qty):
        value = float(qty or 0.0)
        if value.is_integer():
            return str(int(value))
        return ('%.2f' % value).rstrip('0').rstrip('.')

    @api.depends(
        'product_id',
        'product_id.default_code',
        'product_id.product_tmpl_id.name',
        'product_id.product_template_attribute_value_ids.name',
        'product_id.product_template_attribute_value_ids.attribute_id.name',
        'esi_output_line_ids.product_id',
        'esi_output_line_ids.product_id.product_template_attribute_value_ids.name',
        'esi_output_line_ids.product_id.product_template_attribute_value_ids.attribute_id.name',
        'esi_output_line_ids.quantity',
        'move_finished_ids.product_id',
        'move_finished_ids.product_id.product_template_attribute_value_ids.name',
        'move_finished_ids.product_id.product_template_attribute_value_ids.attribute_id.name',
        'move_finished_ids.product_uom_qty',
        'move_finished_ids.state',
        'move_finished_ids.uom_id',
        'uom_id',
    )
    def _compute_esi_batch_display(self):
        for production in self:
            reference = production.product_id
            template = reference.product_tmpl_id
            model_code = production._esi_attribute_value(reference, 'modelo')
            if not model_code:
                code = reference.default_code or template.default_code or ''
                model_code = code.rsplit('-T', 1)[0] if '-T' in code else code
            production.esi_main_product_display = (
                '[%s] %s' % (model_code, template.name) if model_code else template.name
            )

            quantities = {}
            lines = production.esi_output_line_ids.filtered(
                lambda line: line.product_id and line.quantity > 0
            )
            if lines:
                for line in lines:
                    size = production._esi_attribute_value(line.product_id, 'talla')
                    if size:
                        quantities[size] = quantities.get(size, 0.0) + line.quantity
            else:
                moves = production.move_finished_ids.filtered(
                    lambda move: move.state != 'cancel'
                    and move.product_id.product_tmpl_id == template
                    and move.product_uom_qty > 0
                )
                for move in moves:
                    size = production._esi_attribute_value(move.product_id, 'talla')
                    if not size:
                        continue
                    qty = move.uom_id._compute_quantity(
                        move.product_uom_qty, production.uom_id, round=False
                    )
                    quantities[size] = quantities.get(size, 0.0) + qty

            if not quantities:
                size = production._esi_attribute_value(reference, 'talla')
                if size and production.product_qty:
                    quantities[size] = production.product_qty

            rows = sorted(quantities.items(), key=lambda item: production._esi_size_sort_key(item[0]))
            unit = production.uom_id.name or ''
            production.esi_size_quantities_display = ' · '.join(
                '%s = %s %s' % (size, production._esi_qty_text(qty), unit)
                for size, qty in rows
            ) or False
