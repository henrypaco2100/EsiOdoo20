import json
import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError

TARGETS = [('esi.production.group', 'Grupo de fabricación'), ('mrp.bom', 'Componentes de receta'),
           ('stock.picking', 'Transferencia'), ('mrp.production', 'Componentes de OF')]


class VariantGrid(models.TransientModel):
    _name = 'esi.variant.grid'
    _description = 'Cuadrícula de variantes'

    target_model = fields.Selection(TARGETS, required=True, readonly=True)
    target_id = fields.Integer(required=True, readonly=True)
    product_tmpl_id = fields.Many2one('product.template', required=True, string='Producto con variantes', domain="[('type', '=', 'consu')]")
    operation_id = fields.Many2one('mrp.routing.workcenter', string='Consumir en operación', domain="[('bom_id', '=', target_bom_id)]")
    target_bom_id = fields.Many2one('mrp.bom', compute='_compute_target_bom')
    grid_json = fields.Text(string='Tallas y cantidades')

    @api.depends('target_model', 'target_id')
    def _compute_target_bom(self):
        for wizard in self:
            wizard.target_bom_id = False
            if wizard.target_model == 'mrp.bom':
                wizard.target_bom_id = self.env['mrp.bom'].browse(wizard.target_id).exists()
            elif wizard.target_model == 'mrp.production':
                wizard.target_bom_id = self.env['mrp.production'].browse(wizard.target_id).exists().bom_id

    def _target(self):
        self.ensure_one()
        if self.target_model not in dict(TARGETS):
            raise UserError(_('Destino no permitido.'))
        target = self.env[self.target_model].browse(self.target_id).exists()
        if not target:
            raise UserError(_('El documento ya no existe.'))
        target.check_access('write')
        if target.company_id and target.company_id not in self.env.companies:
            raise UserError(_('Active la compañía del documento.'))
        if self.target_model != 'mrp.bom' and target.state != 'draft':
            raise UserError(_('La cuadrícula solo agrega líneas a documentos borrador.'))
        if self.target_model == 'esi.production.group' and target.production_ids:
            raise UserError(_('El grupo ya tiene órdenes.'))
        if self.operation_id:
            if self.target_model not in ('mrp.bom', 'mrp.production'):
                raise UserError(_('Este documento no utiliza operaciones de receta.'))
            bom = target if self.target_model == 'mrp.bom' else target.bom_id
            if self.operation_id.bom_id != bom:
                raise UserError(_('La operación no pertenece a esta receta.'))
        return target

    @api.onchange('product_tmpl_id')
    def _load_grid(self):
        self.grid_json = False
        if self.product_tmpl_id:
            template = self.product_tmpl_id
            template.check_access('read')
            if not template.valid_product_template_attribute_line_ids:
                raise UserError(_('Este producto no tiene atributos para una cuadrícula.'))
            combinations = math.prod(len(l.product_template_value_ids) for l in template.valid_product_template_attribute_line_ids)
            if combinations > 250 or len(template.product_variant_ids) > 250:
                raise UserError(_('Esta cuadrícula admite hasta 250 variantes por producto.'))
            if any(l.attribute_id.create_variant != 'always' for l in template.valid_product_template_attribute_line_ids):
                raise UserError(_('Para esta cuadrícula use atributos con creación de variantes instantánea.'))
            self.grid_json = json.dumps(template._get_template_matrix(display_extra_price=False))

    def action_apply(self):
        self.ensure_one()
        self.check_access('read')
        if self.create_uid != self.env.user:
            raise UserError(_('Este asistente pertenece a otro usuario.'))
        target = self._target()
        template = self.product_tmpl_id
        template.check_access('read')
        if template.type != 'consu':
            raise UserError(_('Seleccione un producto físico, no un servicio.'))
        if template.company_id and template.company_id != target.company_id:
            raise UserError(_('El producto pertenece a otra compañía.'))
        try:
            grid = json.loads(self.grid_json or '{}')
        except (TypeError, ValueError) as exc:
            raise UserError(_('Recargue la cuadrícula.')) from exc
        variants = {tuple(sorted(p.product_template_attribute_value_ids.ids)): p for p in template.product_variant_ids}
        selected = {}
        try:
            cells = [c for row in grid['matrix'] for c in row[1:]]
            if len(cells) > 250:
                raise ValueError()
            for cell in cells:
                qty = float(cell.get('qty', 0))
                if not math.isfinite(qty) or qty < 0:
                    raise ValueError()
                if not qty:
                    continue
                key = tuple(sorted(cell['ptav_ids']))
                product = variants.get(key)
                if not product or product.id in selected or not template._is_combination_possible(product.product_template_attribute_value_ids):
                    raise ValueError()
                product.check_access('read')
                selected[product.id] = (product, qty)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise UserError(_('Cuadrícula inválida: use cantidades positivas y variantes existentes, sin repetir celdas.'))
        if not selected:
            raise UserError(_('Introduzca alguna cantidad mayor que cero.'))
        for product, qty in selected.values():
            if self.target_model == 'esi.production.group':
                if not product.is_storable:
                    raise UserError(_('La salida de fabricación debe controlar existencias.'))
                lines = target.line_ids.filtered(lambda l: l.product_id == product)
                if len(lines) > 1:
                    raise UserError(_('El grupo tiene líneas duplicadas de esa variante.'))
                if lines:
                    lines.quantity += qty
                else:
                    self.env['esi.production.group.line'].create({'group_id': target.id, 'product_id': product.id, 'quantity': qty})
            elif self.target_model == 'mrp.bom':
                self.env['mrp.bom.line'].create({'bom_id': target.id, 'product_id': product.id, 'product_qty': qty,
                    'uom_id': product.uom_id.id, 'operation_id': self.operation_id.id})
            elif self.target_model == 'mrp.production':
                vals = target._get_move_raw_values(product, qty, product.uom_id, operation_id=self.operation_id.id)
                self.env['stock.move'].create(vals)
            else:
                self.env['stock.move'].create({'picking_id': target.id, 'product_id': product.id, 'product_uom_qty': qty,
                    'uom_id': product.uom_id.id, 'company_id': target.company_id.id,
                    'location_id': target.location_id.id, 'location_dest_id': target.location_dest_id.id})
        return {'type': 'ir.actions.act_window_close'}


class GridAction(models.AbstractModel):
    _name = 'esi.variant.grid.action'
    _description = 'Abrir cuadrícula de variantes'

    def action_esi_variant_grid(self):
        self.ensure_one()
        self.check_access('write')
        return {'type': 'ir.actions.act_window', 'name': _('Cuadrícula de variantes'), 'res_model': 'esi.variant.grid',
            'view_mode': 'form', 'target': 'new', 'context': dict(self.env.context,
                default_target_model=self._name, default_target_id=self.id)}


class Group(models.Model):
    _name = 'esi.production.group'
    _inherit = ['esi.production.group', 'esi.variant.grid.action']


class Bom(models.Model):
    _name = 'mrp.bom'
    _inherit = ['mrp.bom', 'esi.variant.grid.action']


class Picking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'esi.variant.grid.action']


class Production(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'esi.variant.grid.action']
