import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Ordered by dependency direction; no SQL table truncation or silent partial deletion.
OPERATIONS = {
    'sales': [('sale.order.line', [('order_id.state', 'in', ['draft', 'sent'])]), ('sale.order', [])],
    'purchases': [('purchase.order.line', []), ('purchase.order', [])],
    'pos': [('pos.payment', []), ('pos.order.line', []), ('pos.order', []), ('pos.session', [])],
    'manufacturing': [('mrp.workorder', []), ('mrp.production', []), ('mrp.unbuild', [])],
    'inventory': [('stock.move.line', []), ('stock.move', []), ('stock.picking', []), ('stock.scrap', []), ('stock.quant', []), ('stock.lot', [])],
    'accounting': [('account.payment', []), ('account.move', [])],
    'expenses': [('hr.expense', []), ('hr.expense.sheet', [])],
    'projects': [('project.task', []), ('project.project', [])],
    'quality': [('quality.check', []), ('quality.alert', [])],
}

class EsiCleanupProfile(models.Model):
    _name = 'esi.cleanup.profile'
    _description = 'Perfil de limpieza de datos de pruebas ESI'
    _order = 'id desc'

    name = fields.Char(string='Nombre del perfil', required=True, default='Limpieza de pruebas')
    scope = fields.Selection([('selected', 'Sucursales seleccionadas'), ('all', 'Todas las sucursales permitidas')], default='selected', required=True, string='Alcance')
    company_ids = fields.Many2many('res.company', 'esi_cleanup_profile_company_rel', 'profile_id', 'company_id', string='Sucursales', default=lambda self: self.env.company)
    mode = fields.Selection([('selective', 'Limpieza selectiva'), ('integral', 'Reinicio integral de datos de prueba')], default='selective', required=True, string='Modalidad')
    sales = fields.Boolean(string='Ventas y cotizaciones')
    purchases = fields.Boolean(string='Compras')
    pos = fields.Boolean(string='Punto de venta')
    manufacturing = fields.Boolean(string='Fabricación')
    inventory = fields.Boolean(string='Movimientos e inventario')
    accounting = fields.Boolean(string='Asientos y facturas')
    expenses = fields.Boolean(string='Gastos')
    projects = fields.Boolean(string='Proyectos')
    quality = fields.Boolean(string='Calidad')
    products = fields.Boolean(string='Productos y variantes')
    bom = fields.Boolean(string='Listas de materiales')
    contacts = fields.Boolean(string='Contactos, excepto los protegidos')
    dashboards = fields.Boolean(string='Tableros de usuarios')
    additional_model = fields.Selection([
        ('crm.lead', 'CRM / oportunidades'), ('mail.activity', 'Actividades'),
        ('stock.warehouse.orderpoint', 'Reglas de reabastecimiento'),
        ('product.pricelist', 'Tarifas de venta'),
    ], string='Modelo adicional autorizado')
    specific_record_ids = fields.Char(string='IDs específicos del modelo (separados por coma)', help='Se aplican solamente al modelo adicional. Ejemplo: 12,15,18')
    sale_status = fields.Selection([('draft', 'Borradores'), ('sent', 'Cotizaciones enviadas'), ('sale', 'Pedidos confirmados'), ('done', 'Finalizados'), ('cancel', 'Cancelados'), ('all', 'Todos los estados')], default='all', required=True, string='Estado de ventas')
    product_ids = fields.Many2many('product.template', 'esi_cleanup_profile_product_rel', 'profile_id', 'product_id', string='Productos específicos')
    preview_text = fields.Text(string='Vista previa de registros', readonly=True, copy=False)
    report_text = fields.Text(string='Informe de ejecución', readonly=True, copy=False)
    confirmation = fields.Char(string='Escriba la frase de confirmación', copy=False)
    last_run = fields.Datetime(string='Última ejecución', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Configurar'), ('preview', 'Previsualizado'), ('done', 'Ejecutado')], default='draft', copy=False)
    protected_contact = fields.Char(string='Contacto protegido por correo', compute='_compute_protected_contact')

    @api.depends_context('uid')
    def _compute_protected_contact(self):
        email = self.env.user.email or self.env.user.partner_id.email or ''
        for rec in self:
            rec.protected_contact = '%s (%s)' % (self.env.user.partner_id.display_name, email)

    def _ensure_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Esta herramienta solo está disponible para administradores de Ajustes.'))

    def _company_ids(self):
        self.ensure_one()
        allowed = set(self.env.user.company_ids.ids)
        selected = allowed if self.scope == 'all' else set(self.company_ids.ids)
        if not selected or not selected.issubset(allowed):
            raise UserError(_('Seleccione sucursales válidas a las que tenga acceso.'))
        return sorted(selected)

    def _ids_filter(self):
        text = (self.specific_record_ids or '').strip()
        if not text:
            return []
        try:
            ids = [int(x.strip()) for x in text.split(',')]
        except (ValueError, TypeError):
            raise UserError(_('Los IDs específicos deben ser números separados por comas.'))
        if not ids or any(x <= 0 for x in ids):
            raise UserError(_('Los IDs específicos deben ser positivos.'))
        return [('id', 'in', ids)]

    def _selected(self):
        names = list(OPERATIONS) if self.mode == 'integral' else [key for key in OPERATIONS if getattr(self, key)]
        extra = ['products', 'bom', 'contacts', 'dashboards'] if self.mode == 'integral' else [key for key in ('products','bom','contacts','dashboards') if getattr(self, key)]
        return names + extra + (['additional'] if self.additional_model else [])

    def _protected_partners(self):
        users = self.env['res.users'].sudo().with_context(active_test=False).search([])
        protected = set(users.mapped('partner_id').ids)
        email = (self.env.user.email or self.env.user.partner_id.email or '').strip().lower()
        if email:
            matches = self.env['res.partner'].sudo().with_context(active_test=False).search([('email', '=ilike', email)])
            protected.update(matches.ids)
        return protected

    def _entries(self):
        self.ensure_one()
        companies = self._company_ids()
        selected = self._selected()
        entries = []
        for key in selected:
            if key in OPERATIONS:
                for model, _unused in OPERATIONS[key]:
                    domain = []
                    if key == 'sales' and model in ('sale.order','sale.order.line') and self.sale_status != 'all' and self.mode != 'integral':
                        state_field = 'state' if model == 'sale.order' else 'order_id.state'
                        domain.append((state_field, '=', self.sale_status))
                    entries.append((key, model, domain))
            elif key == 'products':
                entries.append((key, 'product.template', [('id', 'in', self.product_ids.ids)] if self.product_ids else []))
            elif key == 'bom':
                entries.append((key, 'mrp.bom', [('product_tmpl_id', 'in', self.product_ids.ids)] if self.product_ids else []))
            elif key == 'contacts':
                entries.append((key, 'res.partner', [('id', 'not in', list(self._protected_partners()))]))
            elif key == 'dashboards':
                entries.append((key, 'board.board', []))
            elif key == 'additional':
                entries.append((key, self.additional_model, self._ids_filter()))
        output = []
        for category, name, domain in entries:
            if name not in self.env:
                output.append((category, name, None, 'Modelo no instalado'))
                continue
            Model = self.env[name].sudo().with_context(active_test=False, allowed_company_ids=companies)
            if 'company_id' in Model._fields:
                if category in ('products', 'bom', 'contacts', 'dashboards') and self.scope == 'all' and set(companies) == set(self.env['res.company'].sudo().search([]).ids):
                    domain = ['|', ('company_id', '=', False), ('company_id', 'in', companies)] + domain
                else:
                    domain = [('company_id', 'in', companies)] + domain
            elif category in ('products', 'bom', 'contacts', 'dashboards'):
                if self.scope != 'all' or set(companies) != set(self.env['res.company'].sudo().search([]).ids):
                    output.append((category, name, None, 'Datos compartidos: elija todas las sucursales permitidas'))
                    continue
            else:
                output.append((category, name, None, 'Sin campo company_id: omitido por seguridad'))
                continue
            output.append((category, name, domain, ''))
        return output

    def action_preview(self):
        self.ensure_one()
        self._ensure_admin()
        parts = []
        for category, name, domain, note in self._entries():
            if domain is None:
                parts.append('%s: OMITIDO — %s' % (name, note))
            else:
                count = self.env[name].sudo().with_context(active_test=False).search_count(domain)
                parts.append('%s: %d registros' % (name, count))
        self.write({'preview_text': '\n'.join(parts) or 'No hay categorías seleccionadas.', 'state': 'preview', 'confirmation': False})
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'current'}

    def action_execute(self):
        self.ensure_one()
        self._ensure_admin()
        phrase = 'REINICIAR BASE DE PRUEBAS' if self.mode == 'integral' else 'ELIMINAR DATOS'
        if (self.confirmation or '').strip().upper() != phrase:
            raise UserError(_('Escriba exactamente: %s') % phrase)
        if self.state != 'preview':
            raise UserError(_('Primero genere una vista previa.'))
        entries = self._entries()
        if not entries or not any(domain is not None for _, _, domain, _ in entries):
            raise UserError(_('No hay operaciones válidas para ejecutar.'))
        lines = []
        # Do not mask errors: atomic transaction rolls back if a dependency or business rule blocks unlink.
        for category, name, domain, note in entries:
            if domain is None:
                lines.append('%s: omitido (%s)' % (name, note))
                continue
            Model = self.env[name].sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True, allowed_company_ids=self._company_ids())
            records = Model.search(domain)
            count = len(records)
            if count:
                try:
                    records.unlink()
                except Exception as exc:
                    _logger.exception('ESI cleanup failed for %s', name)
                    raise UserError(_('No se pudo limpiar %s (%s). Toda esta ejecución se revertirá. Error: %s') % (name, count, str(exc))) from exc
            lines.append('%s: %s eliminados' % (name, count))
        self.write({'report_text': '\n'.join(lines), 'confirmation': False, 'state': 'done', 'last_run': fields.Datetime.now()})
        return self._reopen()

    @api.onchange('mode', 'scope', 'company_ids', 'product_ids', 'sale_status', 'specific_record_ids', 'additional_model', 'sales', 'purchases', 'pos', 'manufacturing', 'inventory', 'accounting', 'expenses', 'projects', 'quality', 'products', 'bom', 'contacts', 'dashboards')
    def _onchange_options(self):
        self.state = 'draft'
        self.preview_text = False
        self.confirmation = False
