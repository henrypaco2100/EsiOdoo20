import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from psycopg2 import sql

_logger = logging.getLogger(__name__)

# Ordered by dependency direction; no SQL table truncation or silent partial deletion.
OPERATIONS = {
    'sales': [('sale.order.line', [('order_id.state', 'in', ['draft', 'sent'])]), ('sale.order', [])],
    'purchases': [('purchase.order.line', []), ('purchase.order', [])],
    'pos': [('pos.payment', []), ('pos.order.line', []), ('pos.order', []), ('pos.session', [])],
    'manufacturing': [('mrp.production', []), ('mrp.workorder', []), ('mrp.unbuild', [])],
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
    force_sql = fields.Boolean(string='Forzar DELETE SQL y eliminar dependencias', default=True, help='Elimina dependencias de claves foráneas en profundidad. Solo para bases de pruebas respaldadas.')
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
        # En cualquier modalidad, cada casilla gobierna su propia categoría.
        keys = list(OPERATIONS) + ['products', 'bom', 'contacts', 'dashboards']
        return [key for key in keys if getattr(self, key)] + (['additional'] if self.additional_model else [])

    def _set_all_categories(self, enabled):
        self.ensure_one()
        self._ensure_admin()
        keys = list(OPERATIONS) + ['products', 'bom', 'contacts', 'dashboards']
        values = {key: enabled for key in keys}
        values.update({'state': 'draft', 'preview_text': False, 'confirmation': False})
        # No modificar el modelo adicional: es una selección independiente.
        self.write(values)
        return self._reopen()

    def action_mark_all(self):
        return self._set_all_categories(True)

    def action_clear_all(self):
        return self._set_all_categories(False)

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
                    if key == 'sales' and model in ('sale.order','sale.order.line') and self.sale_status != 'all':
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

    def _prepare_for_removal(self, model_name, records):
        """Use Odoo workflows, not SQL deletes bypassing ORM business invariants."""
        if not records:
            return
        if model_name == 'mrp.production':
            # MO unlink is only supported after its cancellation, and cancelling
            # production also updates linked stock moves and work orders.
            active = records.filtered(lambda r: r.state not in ('draft', 'cancel'))
            if active:
                if 'done' in active.mapped('state'):
                    names = ', '.join(active.filtered(lambda r: r.state == 'done').mapped('name')[:15])
                    raise UserError(_(
                        'Hay fabricaciones FINALIZADAS que no se pueden cancelar directamente: %s. '
                        'Es necesario revertir primero sus movimientos de inventario y valoración. '
                        'No se permite forzar el borrado SQL porque dejaría existencias y asientos inconsistentes.'
                    ) % names)
                method = next((getattr(active, name) for name in ('action_cancel', 'button_cancel')
                               if callable(getattr(active, name, None))), None)
                if not method:
                    raise UserError(_('Esta edición de Fabricación no ofrece un método de cancelación compatible.'))
                method()
                pending = active.filtered(lambda r: r.state != 'cancel')
                if pending:
                    raise UserError(_('No se pudieron cancelar las fabricaciones: %s') % ', '.join(pending.mapped('name')[:15]))
        elif model_name == 'mrp.workorder':
            # Work orders should normally cascade from unlink of their production.
            # Do not attempt to delete completed production work using raw SQL.
            active = records.filtered(lambda r: r.state not in ('cancel', 'pending', 'ready'))
            if active:
                raise UserError(_('Hay órdenes de trabajo activas o terminadas que requieren cancelación desde su fabricación.'))

    def _sql_fk_edges(self):
        """FKs pointing at an ID (or a unique parent key); only ID targets are handled."""
        self.env.cr.execute("""
            SELECT child.relname, att.attname, parent.relname,
                   EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=child.oid
                          AND a.attname='id' AND a.attnum>0 AND NOT a.attisdropped)
            FROM pg_constraint c
            JOIN pg_class child ON child.oid=c.conrelid
            JOIN pg_class parent ON parent.oid=c.confrelid
            JOIN pg_namespace ns ON ns.oid=child.relnamespace
            JOIN pg_attribute att ON att.attrelid=child.oid AND att.attnum=c.conkey[1]
            JOIN pg_attribute pat ON pat.attrelid=parent.oid AND pat.attnum=c.confkey[1]
            WHERE c.contype='f' AND array_length(c.conkey,1)=1
              AND pat.attname='id' AND ns.nspname=current_schema()
              AND child.relkind IN ('r','p')
        """)
        edges = {}
        for child, col, parent, has_id in self.env.cr.fetchall():
            edges.setdefault(parent, []).append((child, col, has_id))
        return edges

    def _sql_company_guard(self, table, ids, allowed, total_scope):
        """Never expand destructive cascades to other companies or protected users."""
        if table in ('res_users', 'res_company', 'ir_module_module', 'esi_cleanup_profile') or table.startswith(('ir_model', 'ir_ui_view', 'ir_actions', 'ir_rule', 'ir_access', 'ir_config_parameter')):
            raise UserError(_('La dependencia alcanza una tabla técnica protegida: %s. No se eliminó nada.') % table)
        if table == 'res_partner':
            protected = self._protected_partners()
            if protected.intersection(ids):
                raise UserError(_('La eliminación afectaría un contacto protegido vinculado a un usuario. Se ha revertido todo.'))
        self.env.cr.execute("""SELECT 1 FROM information_schema.columns
                 WHERE table_schema=current_schema() AND table_name=%s AND column_name='company_id'""", (table,))
        if self.env.cr.fetchone() and not total_scope:
            self.env.cr.execute(sql.SQL('SELECT id FROM {} WHERE id = ANY(%s) AND company_id IS NOT NULL AND NOT(company_id = ANY(%s)) LIMIT 1').format(sql.Identifier(table)), (ids, allowed))
            if self.env.cr.fetchone():
                raise UserError(_('Una dependencia de %s pertenece a otra sucursal. Se cancela todo el borrado.') % table)

    def _sql_delete_tree(self, table, ids, edges, allowed, total_scope, path=None, processed=None):
        """Delete referenced children before their parents, using a single Odoo transaction.

        This follows actual PostgreSQL FKs and handles M2M relation tables without IDs.
        Any unexpected constraint/cycle aborts and rolls back the entire request.
        """
        path = path or set()
        processed = processed if processed is not None else {}
        ids = set(ids) - processed.get(table, set())
        if not ids:
            return 0
        if table in path:
            raise UserError(_('Existe una dependencia circular de SQL en %s. La transacción fue cancelada.') % table)
        self._sql_company_guard(table, list(ids), allowed, total_scope)
        if len(ids) > 300000:
            raise UserError(_('La tabla %s supera el límite de seguridad por lote; divida la operación.') % table)
        subtotal = 0

        # Algunas tablas de negocio (especialmente account_move) tienen claves
        # foráneas que apuntan a la MISMA tabla: reversos, asientos origen, etc.
        # La versión anterior intentaba seguir esas relaciones de forma recursiva
        # y terminaba detectando un falso "ciclo SQL". En una limpieza total de
        # los registros seleccionados, lo correcto es ampliar el conjunto de IDs
        # autorreferenciados y eliminarlos juntos en una sola sentencia DELETE.
        self_edges = [(child, column, has_id) for child, column, has_id in edges.get(table, []) if child == table]
        if self_edges:
            expanded = set(ids)
            changed = True
            while changed:
                changed = False
                base_ids = sorted(expanded)
                for _child, column, has_id in self_edges:
                    if not has_id:
                        continue
                    for start in range(0, len(base_ids), 1000):
                        batch = base_ids[start:start+1000]
                        self.env.cr.execute(
                            sql.SQL('SELECT id FROM {} WHERE {} = ANY(%s)').format(
                                sql.Identifier(table), sql.Identifier(column)
                            ),
                            (batch,),
                        )
                        related = {row[0] for row in self.env.cr.fetchall()}
                        new_ids = related - expanded
                        if new_ids:
                            self._sql_company_guard(table, list(new_ids), allowed, total_scope)
                            expanded.update(new_ids)
                            changed = True
            ids = expanded

        # Procesar únicamente dependencias de OTRAS tablas. Las relaciones
        # autorreferenciadas ya quedaron incluidas en `ids` y se eliminan juntas.
        for child, column, has_id in edges.get(table, []):
            if child == table:
                continue
            for start in range(0, len(ids), 1000):
                batch = sorted(ids)[start:start+1000]
                if has_id:
                    self.env.cr.execute(sql.SQL('SELECT id FROM {} WHERE {} = ANY(%s)').format(sql.Identifier(child), sql.Identifier(column)), (batch,))
                    child_ids = [row[0] for row in self.env.cr.fetchall()]
                    if child_ids:
                        subtotal += self._sql_delete_tree(child, child_ids, edges, allowed, total_scope, path | {table}, processed)
                else:
                    if child.startswith(('res_users', 'ir_')):
                        raise UserError(_('La relación %s está protegida.') % child)
                    self.env.cr.execute(sql.SQL('DELETE FROM {} WHERE {} = ANY(%s)').format(sql.Identifier(child), sql.Identifier(column)), (batch,))
                    subtotal += max(0, self.env.cr.rowcount)
        current = list(ids)
        for start in range(0, len(current), 1000):
            self.env.cr.execute(sql.SQL('DELETE FROM {} WHERE id = ANY(%s)').format(sql.Identifier(table)), (current[start:start+1000],))
            subtotal += max(0, self.env.cr.rowcount)
        processed.setdefault(table, set()).update(ids)
        return subtotal

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
        use_sql = bool(self.force_sql)
        edges = self._sql_fk_edges() if use_sql else {}
        allowed = self._company_ids()
        total_scope = set(allowed) == set(self.env['res.company'].sudo().search([]).ids)
        if use_sql and not total_scope and self.mode == 'integral':
            raise UserError(_('El reinicio integral SQL solo se permite al seleccionar todas las sucursales de la base.'))
        self.env.flush_all()
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
                    if use_sql:
                        if not getattr(Model, '_auto', False):
                            raise UserError(_('El modelo %s no utiliza una tabla SQL automática.') % name)
                        # Explicit SQL bypasses ORM workflows by design for disposable tests.
                        self._sql_delete_tree(Model._table, records.ids, edges, allowed, total_scope)
                        self.env.invalidate_all()
                    else:
                        self._prepare_for_removal(name, records)
                        records = Model.search(domain)
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
