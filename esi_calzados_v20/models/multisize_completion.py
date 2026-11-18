from odoo import models, _
from odoo.exceptions import UserError


class Production(models.Model):
    _inherit = 'mrp.production'

    def _set_qty_producing(self, mark_moves_picked=True):
        # A partial center transfer is a workflow event, not a partial stock output.
        # Native product_qty is the sum of all size allocations for these batches.
        if self.esi_size_batch and self.esi_native_total_mode:
            self.qty_producing = self.product_qty
        return super()._set_qty_producing(mark_moves_picked=mark_moves_picked)

    def _esi_prepare_full_size_completion(self):
        for mo in self:
            if not (mo.esi_size_batch and mo.esi_native_total_mode):
                continue
            if mo.state in ('done', 'cancel'):
                continue
            outputs = mo.move_finished_ids.filtered(lambda m:
                m.state != 'cancel' and m.product_id.product_tmpl_id == mo.product_id.product_tmpl_id)
            if outputs.filtered(lambda m: m.state == 'done'):
                raise UserError(_('Esta orden ya tiene salidas de tallas contabilizadas. Revise esas salidas antes de cerrar el lote completo.'))
            mo.qty_producing = mo.product_qty
            for move in outputs:
                move.quantity = move.product_uom_qty
            # Prepare ordinary planned consumption, preserving explicit actual
            # quantities already marked as picked. Never silently change actuals.
            for move in mo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                if not move.picked:
                    move.quantity = move.product_uom_qty
                    move.picked = True
                elif move.uom_id.compare(move.quantity, move.product_uom_qty) < 0:
                    raise UserError(_(
                        'El componente %(product)s tiene %(actual)s registrados y %(planned)s previstos para el lote completo. '
                        'Revise el consumo antes de finalizar; el avance de un centro no es un consumo parcial de materiales.',
                        product=move.product_id.display_name, actual=move.quantity, planned=move.product_uom_qty))

    def pre_button_mark_done(self):
        self._esi_prepare_full_size_completion()
        return super().pre_button_mark_done()
