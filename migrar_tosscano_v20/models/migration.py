import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import file_open


class Migration(models.Model):
    _name = 'tosscano.migration'
    _description = 'Preparación de migración Tosscano'

    name = fields.Char(default='Migración Tosscano — 23/10/2026', required=True)
    cutoff = fields.Date(default='2026-10-23', readonly=True)
    root_id = fields.Many2one('res.company', string='Matriz TOSSCANO GRUP', required=True)
    factory_id = fields.Many2one('res.company', string='FABRICA CALZADO', required=True)
    cbba_id = fields.Many2one('res.company', string='CBBA', required=True)
    scz_id = fields.Many2one('res.company', string='SCZ', required=True)
    warehouse_factory_id = fields.Many2one('stock.warehouse', string='Almacén fábrica', required=True)
    warehouse_cbba_id = fields.Many2one('stock.warehouse', string='Almacén CBBA', required=True)
    warehouse_scz_id = fields.Many2one('stock.warehouse', string='Almacén SCZ', required=True)
    loaded = fields.Boolean(readonly=True, copy=False)
    line_ids = fields.One2many('tosscano.migration.line', 'migration_id', string='Datos de origen', copy=False)

    def _check_scope(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo los administradores pueden ejecutar la migración.'))
        companies = self.root_id | self.factory_id | self.cbba_id | self.scz_id
        if len(companies) != 4:
            raise UserError(_('Seleccione cuatro compañías diferentes.'))
        if companies - self.env.companies:
            raise UserError(_('Active la matriz y las tres sucursales en el selector de compañías.'))
        for company, warehouse in [(self.factory_id, self.warehouse_factory_id),
                                   (self.cbba_id, self.warehouse_cbba_id),
                                   (self.scz_id, self.warehouse_scz_id)]:
            if company.parent_id != self.root_id or warehouse.company_id != company:
                raise UserError(_('Cada sucursal debe depender directamente de la matriz y su almacén debe pertenecerle.'))
        if self.root_id.parent_id:
            raise UserError(_('La matriz seleccionada no debe tener una compañía superior.'))

    def action_load(self):
        self._check_scope()
        # Serialize two simultaneous clicks and rely on the unique source key.
        self.env.cr.execute('SELECT id FROM tosscano_migration WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset(['loaded'])
        if not self.loaded:
            with file_open('migrar_tosscano_v20/data/source.json', 'r') as stream:
                rows = json.load(stream)
            self.env['tosscano.migration.line'].create([dict(r, migration_id=self.id) for r in rows])
            self.loaded = True
        return self.action_lines()

    def action_lines(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Revisión de datos Tosscano'),
                'res_model': 'tosscano.migration.line', 'view_mode': 'list,form',
                'domain': [('migration_id', '=', self.id)],
                'context': {'search_default_materials': 1}}

    def copy(self, default=None):
        raise UserError(_('No duplique una migración. Use el registro existente para conservar la trazabilidad.'))

    def write(self, vals):
        protected = {'root_id', 'factory_id', 'cbba_id', 'scz_id', 'warehouse_factory_id', 'warehouse_cbba_id', 'warehouse_scz_id', 'cutoff'}
        if protected.intersection(vals) and any(self.mapped('loaded')):
            raise UserError(_('La estructura queda fijada al cargar los datos de origen.'))
        return super().write(vals)


class MigrationLine(models.Model):
    _name = 'tosscano.migration.line'
    _description = 'Dato de migración Tosscano'
    _order = 'kind, id'

    migration_id = fields.Many2one('tosscano.migration', required=True, ondelete='restrict', readonly=True)
    source_key = fields.Char(required=True, readonly=True)
    kind = fields.Selection([('material', 'Materia prima'), ('account', 'Cuenta contable'),
                            ('stock', 'Saldo de inventario'), ('recipe', 'Receta'),
                            ('catalog', 'Catálogo terminado')], required=True, readonly=True)
    code = fields.Char(string='Código propuesto', index=True)
    name = fields.Char(string='Descripción', required=True)
    family = fields.Char(string='Familia')
    subfamily = fields.Char(string='Subfamilia')
    measure = fields.Char(string='Medida')
    material_type = fields.Char(string='Tipo')
    source_uom = fields.Char(string='Unidad de origen', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad de inventario validada')
    component = fields.Boolean(string='Se consume como componente', default=False)
    unit_cost = fields.Float(string='Costo de catálogo (referencia)', readonly=True)
    quantity = fields.Float(string='Saldo de origen', digits='Product Unit', readonly=True)
    branch = fields.Char(string='Sucursal de origen', readonly=True)
    source_json = fields.Text(string='Evidencia original y propuesta', readonly=True)
    issue = fields.Text(string='Observaciones', readonly=True)
    reviewed = fields.Boolean(string='Datos y unidad revisados')
    product_id = fields.Many2one('product.product', readonly=True, string='Producto creado')
    state = fields.Selection([('pending', 'Pendiente'), ('done', 'Importado')], default='pending', readonly=True)
    _source_unique = models.Constraint('UNIQUE(migration_id, source_key)', 'La fila de origen ya está cargada.')

    def write(self, vals):
        if any(line.state == 'done' for line in self):
            raise UserError(_('No modifique una fila importada. Corrija el producto mediante su formulario.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Conserve las filas de origen para la trazabilidad de la migración.'))

    def _validate_material(self):
        self.ensure_one()
        if self.kind != 'material' or not self.reviewed or not self.code or not self.family or not self.subfamily or not self.uom_id:
            raise UserError(_('Revise código, familia, subfamilia y unidad de la materia prima antes de importar.'))
        duplicate = self.search_count([('migration_id', '=', self.migration_id.id), ('kind', '=', 'material'), ('code', '=', self.code), ('id', '!=', self.id)])
        if duplicate:
            raise UserError(_('El código %s continúa duplicado. Resuelva la identidad antes de importar.', self.code))
        products = self.env['product.product'].with_context(active_test=False).search([('default_code', '=', self.code)])
        if products:
            raise UserError(_('Ya existe el código %s. No se modifica ni reutiliza automáticamente un producto existente.', self.code))

    def _category(self, name, parent=False):
        model = self.env['product.category']
        records = model.search([('name', '=', name), ('parent_id', '=', parent.id if parent else False)])
        if len(records) > 1:
            raise UserError(_('Hay categorías duplicadas: %s.', name))
        return records or model.create({'name': name, 'parent_id': parent.id if parent else False})

    def action_import_material(self):
        if not self:
            return
        if len(self.mapped('migration_id')) != 1:
            raise UserError(_('Importe filas de una sola migración a la vez.'))
        migration = self.migration_id
        migration._check_scope()
        # All runs serialize globally, including separate migration records.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(20261023, 27102026)")
        self.invalidate_recordset(['state', 'product_id'])
        pending = self.filtered(lambda line: line.state != 'done')
        for line in pending:
            line._validate_material()
        for line in pending:
            family = line._category(line.family.strip())
            category = line._category(line.subfamily.strip(), family)
            template = self.env['product.template'].with_company(migration.factory_id).create({
                'name': line.name, 'default_code': line.code, 'type': 'consu', 'is_storable': True,
                'company_id': migration.factory_id.id, 'uom_id': line.uom_id.id,
                'categ_id': category.id, 'purchase_ok': True, 'sale_ok': False,
                'esi_component_ok': line.component, 'esi_manufacture_ok': False,
                'esi_measure': line.measure, 'esi_material_type': line.material_type,
            })
            line.write({'product_id': template.product_variant_id.id, 'state': 'done'})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Materias primas importadas'), 'message': _('%s productos creados sin saldos ni valoración.', len(pending)), 'type': 'success', 'sticky': True}}
