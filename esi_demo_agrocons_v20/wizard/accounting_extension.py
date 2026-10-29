from odoo import _, models, fields
from odoo.exceptions import UserError


class AgroAccountingDemoWizard(models.TransientModel):
    _inherit = 'esi.agro.demo.wizard'

    confirm_posted_demo = fields.Boolean(string='Autorizo publicar contabilidad ficticia en esta base de pruebas')

    def action_audit_avco(self):
        self.ensure_one()
        company = self.company_id
        Product = self.env['product.product'].with_company(company).sudo()
        products = Product.search([('default_code', '=like', 'DEMO-AGC-%')])
        if not products:
            raise UserError(_('Primero utilice Crear datos de DEMO.'))
        report = []
        for category in products.mapped('categ_id'):
            fname = 'property_cost_method' if 'property_cost_method' in category._fields else 'cost_method' if 'cost_method' in category._fields else None
            value = getattr(category.with_company(company), fname) if fname else 'CAMPO NO DISPONIBLE'
            report.append('%s: %s' % (category.complete_name, value))
        if any('average' not in line for line in report):
            raise UserError(_('AVCO pendiente en categorías Agrocons:\n%s\nNo se modificó la valoración.') % '\n'.join(report))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('AVCO revisado'), 'message': _('Las categorías agrícolas de la demo usan AVCO. No se modificaron existencias ni movimientos.'),
            'type': 'success', 'sticky': True}}

    def action_create_draft_accounting(self):
        self.ensure_one()
        if not self.confirmation:
            raise UserError(_('Debe confirmar que esta es una base de pruebas.'))
        company = self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active la compañía en el selector antes de continuar.'))
        env = self.with_company(company).env
        Move = env['account.move'].sudo()
        Partner = env['res.partner'].sudo()
        Product = env['product.product'].sudo()
        invoices = [
            ('in_invoice', 'AGC-DEMO-COMPRA-001', 'DEMO - Agroinsumos Oriente SRL', 'DEMO-AGC-SEM-001', 1000, 12),
            ('in_invoice', 'AGC-DEMO-SERVICIO-001', 'DEMO - Servicio Agrícola del Norte', 'DEMO-AGC-REP-001', 5, 125),
            ('out_invoice', 'AGC-DEMO-VENTA-001', 'DEMO - Industria Aceitera del Oriente', 'DEMO-AGC-SOY-001', 1000, 2.5),
        ]
        journals = {}
        for doc_type in ('in_invoice', 'out_invoice'):
            jtype = 'purchase' if doc_type == 'in_invoice' else 'sale'
            journal = env['account.journal'].sudo().search([('company_id', '=', company.id), ('type', '=', jtype)], limit=1)
            if not journal:
                raise UserError(_('Falta un diario de %s para la compañía seleccionada. No se creó ningún documento.') % jtype)
            journals[doc_type] = journal
        for doc_type, reference, partner_name, sku, qty, price in invoices:
            partner = Partner.search([('name', '=', partner_name)], limit=1)
            product = Product.search([('default_code', '=', sku)], limit=1)
            if not partner or not product:
                raise UserError(_('Faltan proveedores, clientes o productos. Primero ejecute Crear datos de DEMO.'))
            existing = Move.search([('company_id', '=', company.id), ('move_type', '=', doc_type), ('ref', '=', reference)], limit=1)
            if existing:
                continue
            income = (product.property_account_income_id or product.categ_id.property_account_income_categ_id)
            expense = (product.property_account_expense_id or product.categ_id.property_account_expense_categ_id)
            acct = income if doc_type == 'out_invoice' else expense
            if not acct:
                raise UserError(_('Configure una cuenta contable de %s para %s. No se crearon documentos.') % ('ingresos' if doc_type == 'out_invoice' else 'gastos', product.display_name))
            Move.create({
                'move_type': doc_type,
                'company_id': company.id,
                'journal_id': journals[doc_type].id,
                'partner_id': partner.id,
                'ref': reference,
                'invoice_line_ids': [(0, 0, {
                    'name': '%s / DEMO Familia Agrocons (sin impuestos calculados)' % product.display_name,
                    'product_id': product.id,
                    'quantity': qty,
                    'price_unit': price,
                    'account_id': acct.id,
                    'tax_ids': [(5, 0, 0)],
                })],
            })
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Contabilidad de DEMO preparada'),
            'message': _('Se prepararon facturas ficticias en borrador. No se publicaron asientos ni se registraron pagos.'),
            'type': 'success', 'sticky': True}}

    def action_create_posted_finance_demo(self):
        """Escenario contable ficticio, deliberadamente separado de los movimientos físicos de stock.

        No genera capas de valoración ni intenta capitalizar cosechas. Solo genera
        apuntes publicados de ejemplo para visualizar libros y reportes financieros.
        """
        self.ensure_one()
        if not self.confirmation or not self.confirm_posted_demo:
            raise UserError(_('Confirme que es una base de pruebas y autorice publicar los asientos ficticios.'))
        company = self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active la compañía seleccionada en el selector de compañías.'))
        env = self.with_company(company).env
        Move = env['account.move'].sudo()
        Account = env['account.account'].sudo()
        Journal = env['account.journal'].sudo()
        Partner = env['res.partner'].sudo()
        tag = 'AGC-CONT-DEMO-2026'
        # Reejecución segura: jamás duplica un escenario ya creado.
        previous = Move.search([('company_id', '=', company.id), ('ref', 'like', tag + '%')], limit=1)
        if previous:
            return self._action_open_posted_demo(company)
        # Escenario contable INDEPENDIENTE de stock y valoración AVCO.
        # Solo debe ejecutarse en base de pruebas, con autorización explícita.
        # Provisión de cuentas aislada a compañía: no altera ni reasigna cuentas existentes.
        def account(types, label, code):
            domain = [('account_type', 'in', types), ('active', '=', True)]
            if 'company_ids' in Account._fields:
                domain.append(('company_ids', 'in', [company.id]))
            elif 'company_id' in Account._fields:
                domain.append(('company_id', '=', company.id))
            existing = Account.search(domain, limit=100)
            # Prefiere una cuenta específica creada anteriormente para esta DEMO.
            specific = existing.filtered(lambda a: a.name == label)
            if specific:
                return specific[0]
            # Para no mezclar partidas ficticias con cuentas operativas,
            # crea una cuenta exclusiva en lugar de tomar la primera que encuentre.
            values = {'name': label, 'account_type': types[0], 'code': code,
                      'reconcile': types[0] in ('asset_receivable', 'liability_payable')}
            if 'company_ids' in Account._fields:
                values['company_ids'] = [(6, 0, [company.id])]
            elif 'company_id' in Account._fields:
                values['company_id'] = company.id
            # Evita colisiones de códigos en cualquier ámbito contable relevante.
            for number in range(0, 90):
                candidate = str(int(code) + number)
                clash_domain = [('code', '=', candidate)]
                if 'company_ids' in Account._fields:
                    clash_domain.append(('company_ids', 'in', [company.id]))
                elif 'company_id' in Account._fields:
                    clash_domain.append(('company_id', '=', company.id))
                if not Account.search(clash_domain, limit=1):
                    values['code'] = candidate
                    return Account.create(values)
            raise UserError(_('No hay código contable libre para %s. No se publicó nada.') % label)

        bank = account(['asset_cash'], 'DEMO Agrocons - Caja y bancos', '119910')
        capital = account(['equity'], 'DEMO Agrocons - Capital', '319910')
        income = account(['income'], 'DEMO Agrocons - Ventas de soya', '419910')
        direct = account(['expense_direct_cost'], 'DEMO Agrocons - Costos de campaña', '519910')
        operating = account(['expense'], 'DEMO Agrocons - Gastos operativos', '539910')
        receivable = account(['asset_receivable'], 'DEMO Agrocons - Clientes por cobrar', '129910')
        payable = account(['liability_payable'], 'DEMO Agrocons - Proveedores por pagar', '219910')

        def journal(kind, label, code):
            j = Journal.search([('company_id', '=', company.id), ('type', '=', kind)], limit=1)
            if j:
                return j
            for index in range(0, 30):
                candidate = code if index == 0 else (code[:3] + str(index))[:5]
                if not Journal.search([('company_id', '=', company.id), ('code', '=', candidate)], limit=1):
                    return Journal.create({'name': label, 'code': candidate,
                                           'type': kind, 'company_id': company.id})
            raise UserError(_('No se pudo preparar el diario %s.') % label)
        general = journal('general', 'DEMO Agrocons Misceláneo', 'AGCM')
        sales = journal('sale', 'DEMO Agrocons Ventas', 'AGCV')
        purchases = journal('purchase', 'DEMO Agrocons Compras', 'AGCP')

        def demo_partner(name, is_customer):
            record = Partner.search([('name', '=', name)], limit=1)
            if not record:
                record = Partner.create({'name': name, 'comment': 'DEMO ficticia Familia Agrocons - ESI'})
            record = record.with_company(company)
            acc_field = 'property_account_receivable_id' if is_customer else 'property_account_payable_id'
            expected = receivable if is_customer else payable
            current = getattr(record, acc_field)
            if not current or current.account_type != expected.account_type:
                # Solo afecta contactos con nombre DEMO, nunca terceros reales.
                record.write({acc_field: expected.id})
            return record
        customer = demo_partner('DEMO - Industria Aceitera del Oriente', True)
        supplier = demo_partner('DEMO - Agroinsumos Oriente SRL', False)
        contractor = demo_partner('DEMO - Servicio Agrícola del Norte', False)
        def entry(ref, date, lines):
            # Cada línea es (descripción, cuenta, debe, haber); nunca sumar el registro account.account.
            debits = round(sum(float(v[2]) for v in lines), 2)
            credits = round(sum(float(v[3]) for v in lines), 2)
            if abs(debits - credits) > 0.001:
                raise UserError(_('El asiento %s no está equilibrado.') % ref)
            existing_entry = Move.search([('company_id', '=', company.id), ('ref', '=', ref),
                                          ('move_type', '=', 'entry')], limit=1)
            if existing_entry:
                return existing_entry
            move = Move.create({'move_type':'entry','company_id':company.id,'journal_id':general.id,
                 'date':date,'ref':ref,'line_ids':[(0,0,{'name':label,'account_id':acct.id,
                    'debit':debit,'credit':credit}) for label,acct,debit,credit in lines]})
            move.action_post()
        def invoice(ref, date, kind, partner, journal_record, expense_account, amount, label):
            existing_invoice = Move.search([('company_id', '=', company.id), ('ref', '=', ref),
                                            ('move_type', '=', kind)], limit=1)
            if existing_invoice:
                return existing_invoice
            move=Move.create({'company_id':company.id,'journal_id':journal_record.id,
                'move_type':kind,'partner_id':partner.id,'invoice_date':date,'date':date,
                'ref':ref,'invoice_line_ids':[(0,0,{'name':label,'quantity':1,
                'price_unit':amount,'account_id':expense_account.id,'tax_ids':[(5,0,0)]})]})
            move.action_post()
        # Incluye capital, caja y bancos, gastos de campaña, facturas y cuentas por cobrar/pagar.
        entry(tag+'-01-CAPITAL','2026-10-02',[
            ('Aporte ficticio de capital',bank,250000,0),
            ('Capital demostrativo',capital,0,250000)])
        entry(tag+'-02-GASTOS','2026-10-08',[
            ('Gastos administrativos agrícolas ficticios',operating,13500,0),
            ('Pago ficticio de gastos',bank,0,13500)])
        invoice(tag+'-03-INSUMOS','2026-10-12','in_invoice',supplier,purchases,direct,40000,
            'Gastos de insumos agrícolas de demostración (sin ingreso a stock)')
        invoice(tag+'-04-SERVICIOS','2026-10-15','in_invoice',contractor,purchases,direct,22000,
            'Servicios agrícolas ficticios de la campaña')
        invoice(tag+'-05-VENTA','2026-10-20','out_invoice',customer,sales,income,185000,
            'Ingreso demostrativo por comercialización de soya (sin salida de stock)')
        return self._action_open_posted_demo(company)

    def action_prepare_and_post_demo(self):
        """Publica el escenario tras preparar cuentas aisladas; conserva las confirmaciones."""
        return self.action_create_posted_finance_demo()

    def _action_open_posted_demo(self, company):
        """Muestra lo publicado para la compañía seleccionada (no toda la contabilidad)."""
        Move = self.env['account.move'].with_company(company).sudo()
        demo = Move.search([('company_id', '=', company.id),
                            ('ref', 'like', 'AGC-CONT-DEMO-2026%')], order='date,id')
        if not demo:
            raise UserError(_('Agrocons no tiene asientos de este escenario en %s. Use Publicar escenario contable DEMO.') % company.display_name)
        return {'type': 'ir.actions.act_window', 'name': _('Asientos publicados – Agrocons'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('id','in',demo.ids)],
                'context': {'search_default_posted': 0}}

    def action_open_posted_demo(self):
        self.ensure_one()
        return self._action_open_posted_demo(self.company_id)

    def action_open_finance(self):
        self.ensure_one()
        action = self.env.ref('esi_finanzas_v20.action_balance', raise_if_not_found=False)
        if not action:
            raise UserError(_('Instale o actualice el módulo esi_finanzas_v20 junto con sus dependencias para consultar Balance General, Resultados, Mayor y Sumas y Saldos. No se cambió la contabilidad.'))
        return action.read()[0]


    def action_check_demo_readiness(self):
        """Diagnóstico no destructivo: ninguna recepción, factura o asiento se valida."""
        self.ensure_one()
        company = self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active la compañía seleccionada antes de continuar.'))
        env = self.with_company(company).env
        Product = env['product.product'].sudo()
        products = Product.search([('default_code', '=like', 'DEMO-AGC-%')])
        issues = []
        if not products:
            issues.append(_('No existen productos Agrocons. Ejecute primero Crear datos de DEMO.'))
        for category in products.mapped('categ_id'):
            key = 'cost_method' if 'cost_method' in category._fields else 'property_cost_method' if 'property_cost_method' in category._fields else None
            value = getattr(category.with_company(company), key) if key else None
            if value != 'average':
                issues.append(_('La categoría %s no tiene AVCO: %s') % (category.display_name, value or _('no disponible')))
        warehouses = env['stock.warehouse'].sudo().search_count([('company_id', '=', company.id)])
        if not warehouses:
            issues.append(_('Falta un almacén configurado para la compañía.'))
        for kind, name in [('purchase', _('Compras')), ('sale', _('Ventas'))]:
            if not env['account.journal'].sudo().search_count([('company_id', '=', company.id), ('type', '=', kind)]):
                issues.append(_('Falta diario contable de %s.') % name)
        if not env['esi.agro.campaign'].sudo().search_count([('company_id', '=', company.id)]):
            issues.append(_('Faltan campañas agrícolas.'))
        if issues:
            raise UserError(_('Revisión preventiva (no se modificaron datos):\n• %s') % '\n• '.join(issues))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Revisión Agrocons'),
            'message': _('Catálogo con AVCO, almacén, diarios y campañas detectados. La prueba de valoración y de movimientos sigue pendiente de ejecutarse en una copia de pruebas.'),
            'type': 'success', 'sticky': True}}

    def action_posted_operational_entries(self):
        """Todas las facturas y asientos PUBLICADOS, no solo el escenario precargado."""
        self.ensure_one()
        company = self.company_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asientos publicados - operaciones de la compañía'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', company.id), ('state', '=', 'posted')],
            'context': {'default_company_id': company.id},
        }

    def action_audit_operational_accounting(self):
        """Diagnóstico de configuración: NUNCA publica ni duplica asientos."""
        self.ensure_one()
        company = self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active primero la compañía elegida en el selector de compañías.'))
        env = self.with_company(company).env
        Journal = env['account.journal']
        Move = env['account.move']
        Account = env['account.account']
        missing = []
        for journal_type, label in [('purchase', 'Compras'), ('sale', 'Ventas'), ('general', 'Misceláneo')]:
            if not Journal.search([('company_id', '=', company.id), ('type', '=', journal_type)], limit=1):
                missing.append('Falta diario: ' + label)
        receivable = Account.search([('account_type', '=', 'asset_receivable')], limit=1)
        payable = Account.search([('account_type', '=', 'liability_payable')], limit=1)
        if not receivable:
            missing.append('Falta cuenta de clientes')
        if not payable:
            missing.append('Falta cuenta de proveedores')
        posted = Move.search_count([('company_id', '=', company.id), ('state', '=', 'posted')])
        drafts = Move.search_count([('company_id', '=', company.id), ('state', '=', 'draft'), ('move_type', 'in', ['in_invoice','out_invoice'])])
        message = '%s: %s asientos/documentos publicados, %s facturas en borrador.' % (company.display_name, posted, drafts)
        if missing:
            message += ' PENDIENTES: ' + '; '.join(missing)
        else:
            message += ' Diarios y cuentas básicas identificados. Confirme cuentas de productos, impuestos y valoración antes de operar.'
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Auditoría de contabilidad operativa'), 'message': message,
            'type': 'warning' if missing or not posted else 'success', 'sticky': True}}
