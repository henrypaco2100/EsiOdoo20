from odoo import api, fields, models, _


class Production(models.Model):
    _inherit = 'mrp.production'

    esi_account_move_count = fields.Integer(
        string='Asientos contables', compute='_compute_esi_account_move_count',
        groups='account.group_account_readonly,account.group_account_invoice')

    def _esi_production_account_moves(self):
        self.ensure_one()
        self.check_access('read')
        moves = (self.move_raw_ids | self.move_finished_ids).account_move_id
        return moves.filtered(lambda m: m.company_id == self.company_id)

    @api.depends('move_raw_ids.account_move_id', 'move_finished_ids.account_move_id')
    def _compute_esi_account_move_count(self):
        for production in self:
            production.esi_account_move_count = len(production._esi_production_account_moves())

    def action_esi_production_account_moves(self):
        self.ensure_one()
        moves = self._esi_production_account_moves()
        moves.check_access('read')
        action = {
            'type': 'ir.actions.act_window', 'name': _('Asientos contables de fabricación'),
            'res_model': 'account.move', 'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'context': {'create': False, 'default_company_id': self.company_id.id},
        }
        if len(moves) == 1:
            action.update(view_mode='form', views=[(self.env.ref('account.view_move_form').id, 'form')], res_id=moves.id)
        return action
