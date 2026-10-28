# -*- coding: utf-8 -*-
"""Importaciones demostrativas: estimaciones separadas de la valoración real.

La única conexión de valoración utiliza stock.landed.cost estándar y requiere
una recepción previamente validada. Nunca se valida desde este módulo.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EsiZeartexImport(models.Model):
    _name = 'esi.zeartex.import'
    _description = 'Zeartex - Expediente de importación de demostración'
    _order = 'code'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    origin_country_id = fields.Many2one('res.country', string='País de origen')
    route = fields.Selection([
        ('sea', 'Marítimo + terrestre'), ('air', 'Aéreo'),
        ('road', 'Terrestre'), ('rail', 'Ferroviario + terrestre')], required=True)
    departure = fields.Char(string='Origen')
    destination = fields.Char(default='Santa Cruz, Bolivia')
    currency_id = fields.Many2one('res.currency', string='Moneda estimación', required=True,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    exchange_rate = fields.Float(string='BOB por USD (solo simulación)', default=6.96, digits=(12, 4))
    goods_usd = fields.Monetary(string='Mercadería USD', currency_field='currency_id')
    line_ids = fields.One2many('esi.zeartex.import.line', 'import_id', string='Gastos estimados')
    expense_total_usd = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    landed_total_usd = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    projected_total_bob = fields.Float(compute='_compute_totals', digits=(16, 2))
    purchase_id = fields.Many2one('purchase.order', string='Orden de compra en borrador', copy=False)
    picking_ids = fields.Many2many('stock.picking', string='Recepciones validadas')
    landed_cost_id = fields.Many2one('stock.landed.cost', string='Costo en destino Odoo', copy=False)
    notes = fields.Text(default='Datos ficticios para demostración. No son una liquidación aduanera oficial.')

    _sql_constraints = [('esi_zea_import_code_company_unique', 'unique(code, company_id)', 'El expediente de Zeartex ya existe para esta compañía.')]

    @api.depends('goods_usd', 'exchange_rate', 'line_ids.amount_usd', 'line_ids.capitalizable')
    def _compute_totals(self):
        for rec in self:
            rec.expense_total_usd = sum(rec.line_ids.mapped('amount_usd'))
            rec.landed_total_usd = rec.goods_usd + sum(rec.line_ids.filtered('capitalizable').mapped('amount_usd'))
            rec.projected_total_bob = rec.landed_total_usd * rec.exchange_rate

    def action_open_landed_cost(self):
        self.ensure_one()
        if not self.landed_cost_id:
            raise UserError(_('Este expediente aún no tiene costo en destino.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.landed.cost',
                'view_mode': 'form', 'res_id': self.landed_cost_id.id}

    def action_prepare_landed_cost(self):
        """Preparar borrador estándar; NUNCA contabilizar ni validar."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo administradores pueden preparar los costos de la DEMO.'))
        if self.landed_cost_id:
            return self.action_open_landed_cost()
        if not self.company_id.currency_id or self.company_id.currency_id.name != 'BOB':
            raise UserError(_('La compañía debe operar en BOB para esta DEMO. No se cambia su moneda automáticamente.'))
        if self.exchange_rate <= 0:
            raise UserError(_('Ingrese un tipo de cambio de simulación positivo.'))
        pickings = self.picking_ids
        if not pickings:
            raise UserError(_('Primero seleccione una recepción de Inventario ya validada en este expediente.'))
        if any(p.company_id != self.company_id or p.state != 'done' for p in pickings):
            raise UserError(_('Todas las recepciones deben estar validadas y pertenecer a esta compañía.'))
        # En AVCO no cambiamos productos ni categorías que tengan historial valorado.
        for picking in pickings:
            for move in picking.move_ids:
                if move.product_id and not move.product_id.product_tmpl_id.esi_zeartex_code:
                    raise UserError(_('La recepción contiene productos ajenos a Zeartex: %s') % move.product_id.display_name)
                if move.product_id and move.product_id.categ_id.property_cost_method != 'average':
                    raise UserError(_('El producto %s no tiene AVCO. Corrija su categoría de forma controlada.') % move.product_id.display_name)
        Journal = self.env['account.journal'].sudo().with_company(self.company_id)
        journal = Journal.search([('company_id', '=', self.company_id.id), ('type', '=', 'general'),
                                  ('name', 'ilike', 'Valuaci')], limit=1)
        if not journal:
            journal = Journal.search([('company_id', '=', self.company_id.id), ('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_('No hay diario general de valoración para esta compañía.'))
        Service = self.env['product.product'].sudo().with_company(self.company_id)
        lines = []
        for expense in self.line_ids.filtered('capitalizable'):
            if expense.amount_usd <= 0:
                continue
            service = Service.search([('default_code', '=', expense.service_code)], limit=1)
            if not service or service.type != 'service':
                raise UserError(_('Falta servicio de costo en destino %s. Cargue primero los escenarios.') % expense.service_code)
            if not service.landed_cost_ok:
                raise UserError(_('El servicio %s debe marcarse como costo en destino.') % service.display_name)
            vals = {'product_id': service.id, 'name': expense.name,
                    'price_unit': expense.amount_usd * self.exchange_rate,
                    'split_method': expense.split_method}
            if expense.account_id:
                vals['account_id'] = expense.account_id.id
            lines.append((0, 0, vals))
        if not lines:
            raise UserError(_('No hay gastos capitalizables para distribuir.'))
        vals = {'company_id': self.company_id.id,
                'account_journal_id': journal.id, 'target_model': 'picking',
                'picking_ids': [(6, 0, pickings.ids)], 'cost_lines': lines,
                'description': 'DEMO ZEARTEX %s - No validar sin revisar cuentas y tipos de cambio' % self.code}
        cost = self.env['stock.landed.cost'].sudo().with_company(self.company_id).create(vals)
        self.landed_cost_id = cost.id
        return self.action_open_landed_cost()


class EsiZeartexImportLine(models.Model):
    _name = 'esi.zeartex.import.line'
    _description = 'Gasto previsto de importación Zeartex'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    import_id = fields.Many2one('esi.zeartex.import', required=True, ondelete='cascade')
    name = fields.Char(required=True)
    service_code = fields.Char(required=True, string='Referencia servicio')
    amount_usd = fields.Float(string='Gasto estimado USD', digits=(14, 2), required=True)
    capitalizable = fields.Boolean(string='Se incorpora al costo', default=True)
    split_method = fields.Selection([
        ('equal','Partes iguales'), ('by_quantity','Por cantidad'),
        ('by_current_cost_price','Por valor'), ('by_weight','Por peso'),
        ('by_volume','Por volumen')], default='by_current_cost_price', required=True)
    account_id = fields.Many2one('account.account', string='Cuenta de gasto (opcional)')
