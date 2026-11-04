from math import isfinite

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class BomCenter(models.Model):
    _name = 'esi.bom.center'
    _description = 'Etapa de la receta por centro de trabajo'
    _order = 'sequence, id'
    _check_company_auto = True

    bom_id = fields.Many2one('mrp.bom', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='bom_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo',
                                  required=True, check_company=True, ondelete='restrict')
    minutes_per_unit = fields.Float(string='Minutos por unidad', default=1.0,
        required=True, help='Tiempo estimado por unidad de medida de la receta. Se multiplica por el total de la orden.')

    @api.constrains('minutes_per_unit', 'bom_id', 'workcenter_id')
    def _check_center(self):
        for line in self:
            if line.minutes_per_unit <= 0:
                raise ValidationError(_('El tiempo estimado del centro debe ser mayor que cero.'))
            if not line.company_id and line.workcenter_id.company_id:
                raise ValidationError(_('Seleccione la sucursal de la receta antes de agregar centros exclusivos de esa sucursal.'))
        self.bom_id._esi_check_center_route()


class Bom(models.Model):
    _inherit = 'mrp.bom'

    esi_center_route_ids = fields.One2many('esi.bom.center', 'bom_id',
                                         string='Recorrido por centros', copy=True)

    @api.constrains('esi_center_route_ids', 'operation_ids', 'type', 'continuous', 'company_id')
    def _esi_check_center_route(self):
        for bom in self.filtered('esi_center_route_ids'):
            if bom.type != 'normal' or bom.continuous:
                raise ValidationError(_('El recorrido por centros requiere una receta de fabricación normal, sin producción continua.'))
            if bom.operation_ids:
                raise ValidationError(_('Use un recorrido por centros o las operaciones de la receta, no ambos. No se han eliminado sus operaciones.'))
            for line in bom.esi_center_route_ids:
                if line.workcenter_id.company_id and line.workcenter_id.company_id != bom.company_id:
                    raise ValidationError(_('Los centros deben pertenecer a la misma sucursal que la receta.'))


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_center_revision = fields.Integer(copy=False)
    esi_center_route = fields.Boolean(compute='_compute_esi_current_center', store=True)
    esi_current_center_id = fields.Many2one('mrp.workcenter', string='Centro actual',
        compute='_compute_esi_current_center', store=True)
    esi_current_center_workorder_id = fields.Many2one('mrp.workorder',
        compute='_compute_esi_current_center', store=True)
    esi_current_center_state = fields.Selection(related='esi_current_center_workorder_id.state')
    esi_center_stage_ids = fields.One2many('mrp.workorder', compute='_compute_esi_center_stages',
        string='Cantidades por centro')

    @api.depends('workorder_ids.esi_center_step')
    def _compute_esi_center_stages(self):
        for production in self:
            production.esi_center_stage_ids = production.workorder_ids.filtered('esi_center_step').sorted('esi_center_step')

    esi_center_progress = fields.Char(string='Recorrido', compute='_compute_esi_current_center')

    @api.depends('state', 'workorder_ids.esi_center_step', 'workorder_ids.state', 'workorder_ids.workcenter_id')
    def _compute_esi_current_center(self):
        for production in self:
            stages = production.workorder_ids.filtered('esi_center_step').sorted('esi_center_step')
            pending = stages.filtered(lambda w: w.state not in ('done', 'cancel'))
            current = pending[:1] if production.state not in ('draft', 'done', 'cancel') else self.env['mrp.workorder']
            production.esi_center_route = bool(stages)
            production.esi_current_center_workorder_id = current
            production.esi_current_center_id = current.workcenter_id
            production.esi_center_progress = _('%(done)s de %(total)s centros terminados',
                done=len(stages.filtered(lambda w: w.state == 'done')), total=len(stages)) if stages else False

    def action_confirm(self):
        for production in self.filtered(lambda p: p.state == 'draft' and p.bom_id.esi_center_route_ids):
            production.bom_id._esi_check_center_route()
            if production.workorder_ids:
                raise UserError(_('La orden ya tiene órdenes de trabajo. Revise el recorrido antes de confirmarla; no se reemplazarán automáticamente.'))
            qty = production.uom_id._compute_quantity(production.product_qty, production.bom_id.uom_id, round=False)
            values = []
            for step, line in enumerate(production.bom_id.esi_center_route_ids.sorted(lambda l: (l.sequence, l.id)), 1):
                if not line.workcenter_id.active:
                    raise UserError(_('El centro %s está archivado.') % line.workcenter_id.display_name)
                values.append({'name': line.workcenter_id.name, 'production_id': production.id,
                    'workcenter_id': line.workcenter_id.id, 'sequence': step * 10,
                    'esi_center_step': step, 'duration_expected': qty * line.minutes_per_unit})
            self.env['mrp.workorder'].with_context(skip_confirm=True).create(values)
        return super().action_confirm()

    def _link_workorders_and_moves(self):
        result = super()._link_workorders_and_moves()
        stages = self.workorder_ids.filtered('esi_center_step').sorted('esi_center_step')
        if stages:
            self.allow_workorder_dependencies = True
            previous = self.env['mrp.workorder']
            for stage in stages:
                stage.blocked_by_workorder_ids = [Command.set(previous.ids)]
                previous = stage
        return result

    def action_esi_advance_center(self):
        self.ensure_one()
        self.check_access('write')
        stage = self.esi_current_center_workorder_id
        if not stage:
            raise UserError(_('No hay un centro pendiente para avanzar en esta orden.'))
        return stage.action_esi_advance_center()

    def action_esi_start_center(self):
        self.ensure_one()
        stage = self.esi_current_center_workorder_id
        if not stage or stage.state != 'ready':
            raise UserError(_('No hay un centro pendiente de inicio.'))
        stage.button_start()
        return True

    def button_mark_done(self):
        for production in self.filtered('esi_center_route'):
            if production.workorder_ids.filtered(lambda w: w.esi_center_step and w.state != 'done'):
                raise UserError(_('Complete todos los centros del recorrido antes de finalizar la fabricación.'))
            production._esi_check_full_center_batch()
        return super().button_mark_done()

    def _esi_check_full_center_batch(self):
        for production in self:
            if production.qty_producing and production.uom_id.compare(production.qty_producing, production.product_qty) != 0:
                raise UserError(_('El recorrido por centros traslada el lote completo. La cantidad en producción debe ser igual al total de la orden.'))

    def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
        if any(p.esi_center_route or p.bom_id.esi_center_route_ids for p in self):
            raise UserError(_('Este recorrido trabaja por lotes completos. Cree órdenes separadas antes de comenzar para fabricar lotes parciales.'))
        return super()._split_productions(amounts, cancel_remaining_qty, set_consumed_qty)

    def write(self, values):
        if 'product_qty' in values:
            for production in self.filtered('esi_center_route'):
                if production.state not in ('draft', 'cancel') and production.uom_id.compare(values['product_qty'], production.product_qty):
                    raise UserError(_('Defina la cantidad total antes de confirmar el recorrido. Para otro lote, cree una nueva orden.'))
        return super().write(values)

    def copy_data(self, default=None):
        values_list = super().copy_data(default=default)
        for production, values in zip(self, values_list):
            if production.esi_center_route:
                # A duplicated MO gets a fresh route when it is confirmed.
                values['workorder_ids'] = []
        return values_list


class Workorder(models.Model):
    _inherit = 'mrp.workorder'

    esi_center_step = fields.Integer(string='Paso del recorrido', readonly=True, copy=True, index=True)
    esi_main_product_display = fields.Char(
        related='production_id.esi_main_product_display', readonly=True)
    esi_size_quantities_display = fields.Char(
        related='production_id.esi_size_quantities_display', readonly=True)

    esi_center_transferred_qty = fields.Float(string='Avanzado', digits='Product Unit', readonly=True, copy=False)
    esi_center_received_qty = fields.Float(string='Recibido', compute='_compute_esi_center_quantities', digits='Product Unit')
    esi_center_available_qty = fields.Float(string='Pendiente en el centro', compute='_compute_esi_center_quantities', digits='Product Unit')

    @api.model
    def action_esi_center_dashboard(self):
        return self.env['ir.actions.actions']._for_xml_id('esi_calzados_v20.center_advance_report_action')

    def _esi_center_amounts(self):
        self.ensure_one()
        if not self.esi_center_step:
            return 0, 0
        mo = self.production_id
        previous = mo.workorder_ids.filtered(
            lambda w: w.esi_center_step and w.esi_center_step < self.esi_center_step
        ).sorted('esi_center_step')[-1:]
        received = (mo.product_qty if not previous or previous.state == 'done'
                    else previous.esi_center_transferred_qty)
        sent = mo.product_qty if self.state == 'done' else self.esi_center_transferred_qty
        return received, max(0, received - sent) if self.state != 'cancel' else 0

    @api.depends('esi_center_step', 'state', 'esi_center_transferred_qty',
                 'production_id.product_qty', 'production_id.workorder_ids.state',
                 'production_id.workorder_ids.esi_center_step',
                 'production_id.workorder_ids.esi_center_transferred_qty')
    def _compute_esi_center_quantities(self):
        for stage in self:
            stage.esi_center_received_qty, stage.esi_center_available_qty = stage._esi_center_amounts()

    def _esi_transfer_center_qty(self, qty):
        self.ensure_one()
        self.check_access('write')
        mo = self.production_id
        mo.check_access('write')
        # Serialize transfers for the entire route, including concurrent transfers at different stages.
        mo.write({'esi_center_revision': mo.esi_center_revision + 1})
        mo.flush_recordset(['esi_center_revision'])
        if not self.esi_center_step or self.state in ('done', 'cancel') or mo.state not in ('confirmed', 'progress', 'to_close'):
            raise UserError(_('Esta etapa ya no admite avances.'))
        uom = mo.uom_id
        if not isfinite(qty) or uom.compare(qty, 0) <= 0:
            raise UserError(_('Ingrese una cantidad mayor que cero.'))
        qty = uom.round(qty)
        received, available = self._esi_center_amounts()
        if uom.compare(qty, available) > 0:
            raise UserError(_('Solo hay %(qty)s disponibles en este centro.', qty=available))
        transferred = uom.round(self.esi_center_transferred_qty + qty)
        super().write({'esi_center_transferred_qty': transferred})
        if uom.compare(transferred, mo.product_qty) == 0:
            # Close the work order without native button_finish, which also marks
            # raw moves and byproducts as picked. Progress is not a stock posting.
            self._esi_check_previous_centers()
            self.end_all()
            now = fields.Datetime.now()
            self.with_context(bypass_duration_calculation=True, bypass_change_producing=True).write({
                'state': 'done', 'qty_produced': mo.product_qty,
                'date_start': self.date_start or now, 'date_finished': now,
                'costs_hour': self.workcenter_id.costs_hour,
            })
        following = mo.workorder_ids.filtered(
            lambda w: w.esi_center_step > self.esi_center_step).sorted('esi_center_step')[:1]
        self.env['esi.center.advance'].sudo().create({
            'company_id': mo.company_id.id, 'workorder_id': self.id,
            'workcenter_id': self.workcenter_id.id, 'quantity': qty,
            'uom_id': uom.id, 'operator_id': self.env.uid,
        })
        mo.message_post(body=_('Avance: %(qty)s %(unit)s · %(source)s → %(destination)s. Quedan %(remaining)s en el centro de origen.',
            qty=qty, unit=uom.name, source=self.workcenter_id.display_name,
            destination=following.workcenter_id.display_name if following else _('Recorrido terminado'),
            remaining=self._esi_center_amounts()[1]))
        return {'type': 'ir.actions.act_window_close'}

    def unlink(self):
        if self.filtered(lambda w: w.esi_center_step and w.production_id.state not in ('draft', 'cancel')):
            raise UserError(_('No elimine etapas de un recorrido confirmado. Cancele la orden si necesita rehacer el recorrido.'))
        return super().unlink()

    def _esi_check_previous_centers(self):
        for stage in self.filtered('esi_center_step'):
            if stage.production_id.state not in ('confirmed', 'progress', 'to_close'):
                raise UserError(_('Confirme la fabricación antes de trabajar en sus centros.'))
            previous = stage.production_id.workorder_ids.filtered(
                lambda w: w.esi_center_step and w.esi_center_step < stage.esi_center_step)
            if any(w.state != 'done' for w in previous):
                raise UserError(_('Termine el centro anterior antes de continuar con este.'))
            stage.production_id._esi_check_full_center_batch()

    def button_start(self, raise_on_invalid_state=False):
        self._esi_check_previous_centers()
        return super().button_start(raise_on_invalid_state=raise_on_invalid_state)

    def button_finish(self):
        if self.filtered(lambda w: w.esi_center_step and w.state not in ('done', 'cancel')):
            raise UserError(_('Use Registrar avance para indicar la cantidad terminada en el centro.'))
        self._esi_check_previous_centers()
        return super().button_finish()

    def write(self, values):
        if 'esi_center_transferred_qty' in values:
            raise UserError(_('Use Registrar avance para modificar la cantidad trasladada.'))
        if values.get('state') == 'done':
            for stage in self.filtered(lambda w: w.esi_center_step and w.state != 'done'):
                mo = stage.production_id
                if mo.uom_id.compare(stage.esi_center_transferred_qty, mo.product_qty) != 0:
                    raise UserError(_('Registre toda la cantidad de este centro antes de cerrarlo.'))
        if values.get('state') in ('progress', 'done'):
            self._esi_check_previous_centers()
        if 'workcenter_id' in values:
            for stage in self.filtered('esi_center_step'):
                if values['workcenter_id'] != stage.workcenter_id.id:
                    raise UserError(_('Para trasladar la orden use Finalizar centro y avanzar. Cambiar la tarjeta de columna no registra el recorrido.'))
        return super().write(values)

    def _action_plan(self, from_date=False, alternative=True, consider_blocked_by=True,
                     ignore_schedule=False, leaves_to_ignore=False):
        if self.filtered('esi_center_step'):
            alternative = False
        return super()._action_plan(from_date=from_date, alternative=alternative,
            consider_blocked_by=consider_blocked_by, ignore_schedule=ignore_schedule,
            leaves_to_ignore=leaves_to_ignore)

    def action_esi_advance_center(self):
        self.ensure_one()
        self.check_access('write')
        if not self.esi_center_step or self.esi_center_available_qty <= 0 or self.production_id.state not in ('confirmed', 'progress', 'to_close'):
            raise UserError(_('No hay cantidad pendiente disponible en este centro.'))
        wizard = self.env['esi.center.transfer'].create({'workorder_id': self.id, 'quantity': self.esi_center_available_qty})
        return {'type': 'ir.actions.act_window', 'name': _('Registrar avance'),
                'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}


class CenterTransfer(models.TransientModel):
    _name = 'esi.center.transfer'
    _description = 'Avance parcial por centro de trabajo'

    workorder_id = fields.Many2one('mrp.workorder', required=True, readonly=True, ondelete='cascade')
    available_qty = fields.Float(related='workorder_id.esi_center_available_qty', string='Pendiente en este centro')
    quantity = fields.Float(string='Cantidad a avanzar', required=True, digits='Product Unit')

    def action_transfer(self):
        self.ensure_one()
        self.check_access('write')
        return self.workorder_id._esi_transfer_center_qty(self.quantity)
