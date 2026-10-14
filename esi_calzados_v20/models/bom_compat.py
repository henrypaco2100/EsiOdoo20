from odoo import api, models, _
from odoo.exceptions import UserError
from .virtual_commands import clean_virtual_commands


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def _esi_clean_web_rows(self, values):
        values = dict(values)
        try:
            for name in ('bom_line_ids', 'byproduct_ids', 'operation_ids'):
                if name in values:
                    values[name] = clean_virtual_commands(values[name])
        except ValueError as exc:
            raise UserError(_('%s', str(exc))) from exc
        return values

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._esi_clean_web_rows(v) for v in vals_list])

    def write(self, values):
        return super().write(self._esi_clean_web_rows(values))
