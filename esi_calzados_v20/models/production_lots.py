from odoo import _, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _esi_shared_output_lot_name(self):
        """Return the single batch lot name chosen on a multi-size MO.

        Odoo's native ``lot_producing_ids`` belongs to the reference product of
        the MO.  In an ESI multi-size MO the other sizes are native by-products,
        therefore each product needs its own ``stock.lot`` record even when the
        business batch number is the same.
        """
        self.ensure_one()
        if not (self.esi_variant_line_mode or self.esi_size_batch):
            return False
        if self.product_id.tracking == 'serial':
            raise UserError(_(
                'La fabricación multitalle con un lote común requiere seguimiento '
                '"Por lotes", no "Por número de serie", en los productos terminados.'
            ))
        if not self.lot_producing_ids:
            return False
        if len(self.lot_producing_ids) != 1:
            raise UserError(_('Indique un único lote para toda la orden multitalle.'))
        return self.lot_producing_ids.name

    def _esi_output_lot(self, product, lot_name):
        self.ensure_one()
        Lot = self.env['stock.lot'].with_company(self.company_id)
        lot = Lot.search([
            ('product_id', '=', product.id),
            ('name', '=', lot_name),
            ('company_id', 'in', [False, self.company_id.id]),
        ], order='company_id desc, id', limit=1)
        if not lot:
            lot = Lot.create({
                'name': lot_name,
                'product_id': product.id,
                'company_id': self.company_id.id,
                'ref': self.name,
            })
        elif not lot.ref:
            # The lot remains product-specific; the MO reference makes the
            # common production batch explicit on the lot form as well.
            lot.ref = self.name
        return lot

    def _esi_apply_shared_lot_to_outputs(self):
        """Propagate the MO batch name to every size output.

        A same lot *name* is intentionally reused across the different product
        variants.  Odoo stores one stock.lot per product, so traceability stays
        correct while operators work with one physical production batch code.
        """
        MoveLine = self.env['stock.move.line']
        for production in self:
            lot_name = production._esi_shared_output_lot_name()
            if not lot_name:
                continue

            outputs = production.move_finished_ids.filtered(
                lambda move: move.state not in ('done', 'cancel')
                and move.product_id.product_tmpl_id == production.product_id.product_tmpl_id
            )
            for move in outputs:
                tracking = move.product_id.tracking
                if tracking == 'none':
                    continue
                if tracking == 'serial':
                    raise UserError(_(
                        'La variante %s está configurada por número de serie. '
                        'Para compartir un lote de fabricación entre tallas, configure '
                        'los productos terminados con seguimiento Por lotes.'
                    ) % move.product_id.display_name)

                lot = production._esi_output_lot(move.product_id, lot_name)
                conflicting = move.move_line_ids.filtered(
                    lambda line: (line.lot_id and line.lot_id != lot)
                    or (line.lot_name and line.lot_name != lot_name)
                )
                if conflicting:
                    raise UserError(_(
                        'La salida %s ya tiene un lote diferente asignado. '
                        'Quite ese lote o use una nueva orden antes de finalizar.'
                    ) % move.product_id.display_name)

                lines_without_lot = move.move_line_ids.filtered(
                    lambda line: not line.lot_id and not line.lot_name
                )
                if lines_without_lot:
                    lines_without_lot.write({'lot_id': lot.id, 'lot_name': False})

                # Finished moves bypass reservation.  If Odoo has not created a
                # move line yet, create the produced line with the planned output
                # quantity so stock validation sees both quantity and lot.
                if not move.move_line_ids and move.uom_id.compare(move.product_uom_qty, 0.0) > 0:
                    vals = move._prepare_move_line_vals(quantity=move.product_uom_qty)
                    vals.update({'lot_id': lot.id, 'lot_name': False})
                    MoveLine.create(vals)

                # In case a zero/technical line existed and no positive line was
                # created, ensure the planned batch still has a lot-bearing line.
                positive_lines = move.move_line_ids.filtered(
                    lambda line: line.uom_id.compare(line.quantity, 0.0) > 0
                )
                if not positive_lines and move.uom_id.compare(move.product_uom_qty, 0.0) > 0:
                    vals = move._prepare_move_line_vals(quantity=move.product_uom_qty)
                    vals.update({'lot_id': lot.id, 'lot_name': False})
                    MoveLine.create(vals)

    def pre_button_mark_done(self):
        # Core Odoo creates/validates the reference-product lot before calling
        # this hook.  Run its normal checks first, then propagate the same batch
        # name to the remaining size outputs just before stock posting.
        result = super().pre_button_mark_done()
        if result is not True:
            return result
        self._esi_apply_shared_lot_to_outputs()
        return True
