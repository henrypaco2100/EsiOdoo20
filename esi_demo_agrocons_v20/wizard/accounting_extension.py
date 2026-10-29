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
            raise UserError(_('Ya existe un escenario contable Agrocons con referencia %s. No se duplicaron registros.') % tag)
        # Evitar mezclar contabilidad ficticia con datos ajenos en compañías activas.
        # Confirmación expresa, preflight y ausencia de cambios sobre cuentas compartidas.
        products = env['product.product'].sudo().search([('default_code', '=like', 'DEMO-AGC-%')])
        if not products:
            raise UserError(_('Primero ejecute Crear datos de DEMO y verifique AVCO.'))
        for category in products.mapped('categ_id'):
            key = 'cost_method' if 'cost_method' in category._fields else 'property_cost_method' if 'property_cost_method' in category._fields else None
            if not key or getattr(category.with_company(company), key) != 'average':
                raise UserError(_('AVCO pendiente en %s. No se publicaron asientos.') % category.display_name)
        # account.account usa company_ids en Odoo 20; las cuentas se buscan en contexto empresa.
        def account(types, keywords=()):
            domain = [('account_type', 'in', types), ('active', '=', True)]
            if 'company_ids' in Account._fields:
                domain.append(('company_ids', 'in', [company.id]))
            elif 'company_id' in Account._fields:
                domain.append(('company_id', '=', company.id))
            matches = Account.search(domain, limit=200)
            for keyword in keywords:
                found = matches.filtered(lambda a: keyword.lower() in a.name.lower())
                if found:
                    return found[0]
            return matches[:1]
        bank = account(['asset_cash'], ('banco', 'caja'))
        capital = account(['equity'], ('capital social', 'capital'))
        income = account(['income'], ('ventas', 'ingreso'))
        direct = account(['expense_direct_cost', 'expense'], ('insumo', 'costo', 'material'))
        operating = account(['expense', 'expense_other'], ('administraci', 'servicio', 'gasto'))
        missing = [name for name, item in [('Banco/Caja',bank),('Patrimonio/Capital',capital),('Ingresos',income),('Costos o gastos',direct),('Gastos operativos',operating)] if not item]
        if missing:
            raise UserError(_('Faltan cuentas compatibles para: %s. Revise el plan de cuentas de la empresa.') % ', '.join(missing))
        def journal(kind):
            j = Journal.search([('company_id', '=', company.id), ('type', '=', kind)], limit=1)
            if not j:
                raise UserError(_('No existe diario de tipo %s para la compañía seleccionada.') % kind)
            return j
        general, sales, purchases = journal('general'), journal('sale'), journal('purchase')
        customer = Partner.search([('name', '=', 'DEMO - Industria Aceitera del Oriente')], limit=1)
        supplier = Partner.search([('name', '=', 'DEMO - Agroinsumos Oriente SRL')], limit=1)
        contractor = Partner.search([('name', '=', 'DEMO - Servicio Agrícola del Norte')], limit=1)
        if not customer or not supplier or not contractor:
            raise UserError(_('Faltan clientes/proveedores ficticios. Ejecute primero Crear datos de DEMO.'))
        # Validación previa de cuentas de tercero; Odoo generará CxC y CxP por factura.
        for partner, expected_type in [(customer,'asset_receivable'),(supplier,'liability_payable'),(contractor,'liability_payable')]:
            field = 'property_account_receivable_id' if expected_type == 'asset_receivable' else 'property_account_payable_id'
            acc = getattr(partner.with_company(company), field, False)
            if not acc or acc.account_type != expected_type:
                raise UserError(_('Configure la cuenta de tercero para %s antes de continuar.') % partner.name)
        # Todos los importes son ficticios en la moneda principal de la compañía.
        # Fechas de octubre 2026 para que los reportes filtrados a ese mes tengan datos.
        def entry(ref, date, lines):
            debits = round(sum(v[1] for v in lines), 2)
            credits = round(sum(v[2] for v in lines), 2)
            if abs(debits - credits) > 0.001:
                raise UserError(_('El asiento %s no está equilibrado.') % ref)
            move = Move.create({'move_type':'entry','company_id':company.id,'journal_id':general.id,
                 'date':date,'ref':ref,'line_ids':[(0,0,{'name':label,'account_id':acct.id,
                    'debit':debit,'credit':credit}) for label,acct,debit,credit in lines]})
            move.action_post()
        def invoice(ref, date, kind, partner, journal_record, expense_account, amount, label):
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
        return {'type':'ir.actions.client','tag':'display_notification','params':{
            'title':_('Contabilidad ficticia publicada'),
            'message':_('Se publicaron cinco documentos de demostración (capital, gastos, dos facturas de compra y una de venta). Abra los reportes financieros ESI con fechas del 1 al 28 de octubre de 2026 y Solo asientos publicados activado. No se alteró el stock ni se contabilizó costo de cosecha.'),
            'type':'success','sticky':True}}

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
