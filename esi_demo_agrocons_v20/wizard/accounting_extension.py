from odoo import _, models
from odoo.exceptions import UserError


class AgroAccountingDemoWizard(models.TransientModel):
    _inherit = 'esi.agro.demo.wizard'

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

    def action_open_finance(self):
        self.ensure_one()
        action = self.env.ref('esi_finanzas_v20.action_balance', raise_if_not_found=False)
        if not action:
            raise UserError(_('Instale o actualice el módulo esi_finanzas_v20 junto con sus dependencias para consultar Balance General, Resultados, Mayor y Sumas y Saldos. No se cambió la contabilidad.'))
        return action.read()[0]
