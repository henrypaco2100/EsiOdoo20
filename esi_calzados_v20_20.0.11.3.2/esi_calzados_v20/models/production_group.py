from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EsiProductionGroup(models.Model):
    _name = 'esi.production.group'
    _description = 'Grupo de fabricación'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Referencia', default='Nuevo', readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Sucursal / Compañía', required=True, default=lambda self: self.env.company)
    responsible_id = fields.Many2one('res.users', string='Responsable de fabricación', tracking=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
    )
    line_ids = fields.One2many('esi.production.group.line', 'group_id', string='Productos')
    production_ids = fields.One2many('mrp.production', 'esi_group_id', string='Órdenes de fabricación', readonly=True)
    production_count = fields.Integer(string='Órdenes de fabricación', compute='_compute_production_count', store=True)
    state = fields.Selection([('draft','Borrador'),('created','OF creadas'),('cancel','Cancelado')], default='draft', tracking=True, string='Estado')
    note = fields.Text(string='Notas internas')

    @api.depends('production_ids')
    def _compute_production_count(self):
        for rec in self:
            rec.production_count = len(rec.production_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('esi.production.group') or 'Nuevo'
        return super().create(vals_list)

    def action_create_productions(self):
        for group in self:
            if group.state != 'draft':
                continue
            if not group.responsible_id:
                raise UserError(_('Seleccione un responsable de fabricación.'))
            if not group.line_ids:
                raise UserError(_('Agregue al menos un producto al grupo.'))
            vals_list = []
            for line in group.line_ids:
                if line.quantity <= 0:
                    raise UserError(_('La cantidad debe ser mayor que cero.'))
                product = line.product_id
                bom = line.bom_id or self.env['mrp.bom']._bom_find(product, company_id=group.company_id.id, bom_type='normal').get(product)
                if not bom:
                    raise UserError(_('No existe una lista de materiales para %s.') % product.display_name)
                vals_list.append({
                    'product_id': product.id,
                    'product_qty': line.quantity,
                    'uom_id': line.uom_id.id,
                    'bom_id': bom.id,
                    'company_id': group.company_id.id,
                    'origin': group.name,
                    'esi_group_id': group.id,
                    'esi_responsible_id': group.responsible_id.id or False,
                    'esi_analytic_account_id': group.analytic_account_id.id or False,
                })
            productions = self.env['mrp.production'].with_company(group.company_id).create(vals_list)
            productions.action_confirm()
            group.state = 'created'
        return True

    def action_view_productions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Órdenes de fabricación'),
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [('esi_group_id', '=', self.id)],
            'context': {'default_esi_group_id': self.id},
        }

    def action_cancel(self):
        self.write({'state':'cancel'})
        return True


class EsiProductionGroupLine(models.Model):
    _name = 'esi.production.group.line'
    _description = 'Línea de grupo de fabricación'

    group_id = fields.Many2one('esi.production.group', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto / variante', required=True, domain="[('is_storable', '=', True), ('esi_manufacture_ok', '=', True)]")
    quantity = fields.Float(string='Cantidad', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad', related='product_id.uom_id', readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='Lista de materiales', domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id', store=False)
