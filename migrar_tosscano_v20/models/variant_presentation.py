from decimal import Decimal, InvalidOperation
from odoo import api, fields, models, _
from odoo.exceptions import UserError


def size_sort_key(name):
    label = str(name or '').strip()
    try:
        value = Decimal(label.replace(',', '.'))
        if value.is_finite():
            return (0, value, label)
    except InvalidOperation:
        pass
    return (1, Decimal(0), label.casefold())


class VariantPresentation(models.Model):
    _inherit = 'tosscano.migration'

    def _sort_size_values(self, attribute):
        values = self.env['product.attribute.value'].with_context(lang=None).search([
            ('attribute_id', '=', attribute.id)], order='id')
        for sequence, value in enumerate(sorted(values, key=lambda v: (size_sort_key(v.name), v.id)), 1):
            if value.sequence != sequence:
                value.write({'sequence': sequence})

    def _set_footwear_matrix(self, template):
        if 'product_add_mode' not in template._fields:
            raise UserError(_('Instale Selección de variantes por cuadrícula en ventas (sale_product_matrix).'))
        if template.product_add_mode != 'matrix':
            template.write({'product_add_mode': 'matrix'})
        for line in template.attribute_line_ids:
            if (line.attribute_id.with_context(lang=None).name or '').strip().casefold() == 'talla':
                self._sort_size_values(line.attribute_id)

    def _set_finished_lot_tracking(self, template):
        if template.tracking == 'lot':
            return True
        variants = template.with_context(active_test=False).product_variant_ids
        # Check all companies; do not change tracking over existing unassigned stock.
        if self.env['stock.quant'].sudo().search_count([
            ('product_id', 'in', variants.ids), ('location_id.usage', 'in', ['internal', 'transit']),
            '|', '|', ('quantity', '!=', 0), ('reserved_quantity', '!=', 0),
            ('inventory_quantity_set', '=', True),
        ], limit=1):
            return False
        if self.env['stock.move'].sudo().search_count([
            ('product_id', 'in', variants.ids), ('state', 'not in', ['done', 'cancel']),
        ], limit=1):
            return False
        template.write({'tracking': 'lot'})
        return True

    def _finished(self, row):
        result = super()._finished(row)
        template = self._ref(row['key'])
        if template and not self._finished_conflict(row):
            self._set_footwear_matrix(template)
            self._set_finished_lot_tracking(template)
        return result

    def action_fix_size_order_matrix(self):
        self.ensure_one()
        self._lock()
        templates = self.env['product.template']
        for row in self._source()['finished']:
            template = self._ref(row['key'])
            if template:
                templates |= template
        pending = []
        for template in templates:
            self._set_footwear_matrix(template)
            if not self._set_finished_lot_tracking(template):
                pending.append(template.display_name)
        self.import_log = (self.import_log or '') + '\n' + _(
            'Tallas en orden numérico ascendente y selección Matrix aplicada a %s calzados migrados.', len(templates))
        if pending:
            self.import_log += '\n' + _('Seguimiento pendiente: tienen saldo, conteos o movimientos abiertos: %s', ', '.join(pending))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Calzados actualizados'), 'message': _('Tallas ordenadas en %s productos. Seguimiento por lotes pendiente en %s; consulte Resultado.', len(templates), len(pending)),
            'type': 'success', 'sticky': False, 'next': {'type': 'ir.actions.client', 'tag': 'reload'}}}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('attribute_line_ids.value_ids', 'attribute_line_ids.value_ids.name',
                 'attribute_line_ids.attribute_id.name', 'attribute_line_ids.attribute_id.esi_highlight_card')
    def _compute_esi_variant_highlight(self):
        super()._compute_esi_variant_highlight()
        for template in self:
            lines = template.attribute_line_ids.filtered(lambda line: line.attribute_id.esi_highlight_card)
            parts = []
            for line in lines:
                names = line.value_ids.mapped('name')
                if (line.attribute_id.with_context(lang=None).name or '').strip().casefold() == 'talla':
                    names = sorted(names, key=size_sort_key)
                parts.append('%s: %s' % (line.attribute_id.name, ' / '.join(names)))
            template.esi_variant_highlight = ' · '.join(parts)


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    tosscano_is_size = fields.Boolean(compute='_compute_tosscano_is_size')

    @api.depends('attribute_id', 'attribute_id.name')
    def _compute_tosscano_is_size(self):
        for line in self:
            name = line.attribute_id.with_context(lang=None).name or ''
            line.tosscano_is_size = name.strip().casefold() == 'talla'
