# -*- coding: utf-8 -*-
"""Escenario contable de demostración; NO crea ni valora inventario.

Las facturas de compra/venta ordinarias se contabilizan mediante el flujo
estándar de Odoo al publicarse. No se añaden hooks que dupliquen asientos.
"""
from odoo import fields, models, _
from odoo.exceptions import UserError

TAG = 'ZEA-CONT-DEMO-2026'


class EsiZeartexAccountingDemo(models.Model):
    _inherit = 'esi.zeartex.demo'

    confirm_posted_accounting = fields.Boolean(
        string='Autorizo publicar asientos y facturas ficticias en una base exclusivamente de pruebas',
        default=False, copy=False)

    def action_post_accounting_demo(self):
        self.ensure_one()
        company = self._company()
        if not self.confirm_posted_accounting:
            raise UserError(_('Debe marcar la autorización de publicación CONTABLE en base de pruebas.'))
        if company not in self.env.companies:
            raise UserError(_('Active la compañía seleccionada en el selector de Odoo antes de continuar.'))
        if company.currency_id.name != 'BOB':
            raise UserError(_('Esta demostración contable utiliza importes ficticios en BOB. No cambiaremos la moneda de la compañía.'))
        env = self.with_company(company).env
        Account = env['account.account'].sudo()
        Journal = env['account.journal'].sudo()
        Partner = env['res.partner'].sudo()
        Move = env['account.move'].sudo()
        Product = env['product.template'].sudo()

        # Exclusivamente después de cargar catálogo, proveedores y clientes.
        if not Product.search_count([('esi_zeartex_code', '=like', 'ZEA-%'), ('company_id', '=', company.id)]):
            raise UserError(_('Primero cargue el catálogo DEMO Zeartex.'))
        existing = Move.search([('company_id', '=', company.id), ('ref', 'like', TAG + '%')], limit=1)
        if existing:
            return self._action_open_posted_demo(company)

        def account_by_type(types, preferred_codes=(), keywords=()):
            domain = [('account_type', 'in', list(types)), ('active', '=', True)]
            if 'company_ids' in Account._fields:
                domain.append(('company_ids', 'in', [company.id]))
            elif 'company_id' in Account._fields:
                domain.append(('company_id', '=', company.id))
            candidates = Account.search(domain)
            for code in preferred_codes:
                found = candidates.filtered(lambda a: a.code == code)
                if found:
                    return found[0]
            for keyword in keywords:
                found = candidates.filtered(lambda a: keyword.casefold() in a.name.casefold())
                if found:
                    return found[0]
            return candidates[:1] if len(candidates) == 1 else Account.browse()

        bank = account_by_type(('asset_cash',), ('111301',), ('Banco', 'Caja'))
        equity = account_by_type(('equity',), ('310100',), ('Capital',))
        sales = account_by_type(('income',), ('410100',), ('Ventas',))
        expense = account_by_type(('expense', 'expense_other'), ('530080',), ('Administración', 'Gastos'))
        direct = account_by_type(('expense_direct_cost',), (), ('Costo de ventas', 'Mercaderías vendidas'))
        # No sustituimos costo de ventas por una cuenta arbitraria de inventarios.
        if not direct:
            direct = account_by_type(('expense',), (), ('Costo de ventas', 'Costos de mercadería', 'Compras de mercadería'))
        missing = [label for label, rec in [('Caja/Banco', bank), ('Capital', equity),
                    ('Ventas', sales), ('Gastos operativos', expense), ('Costo comercial', direct)] if not rec]
        if missing:
            raise UserError(_('Faltan cuentas contables adecuadas para: %s. Configure cuentas de la DEMO; no se publicó nada.') % ', '.join(missing))
        # No usar la misma cuenta como costo de mercadería y gasto administrativo.
        if direct == expense:
            raise UserError(_('La cuenta de costo comercial no puede ser igual a gastos administrativos. Configure una cuenta separada.'))

        def journal(kind):
            found = Journal.search([('company_id', '=', company.id), ('type', '=', kind)], limit=1)
            if not found:
                raise UserError(_('No existe diario contable de tipo %s para la compañía.') % kind)
            return found
        general, sale_journal, purchase_journal = journal('general'), journal('sale'), journal('purchase')
        supplier = Partner.search([('ref', '=', 'ZEA-PROV-01')], limit=1)
        supplier2 = Partner.search([('ref', '=', 'ZEA-PROV-06')], limit=1)
        customer = Partner.search([('ref', '=', 'ZEA-CLI-01')], limit=1)
        customer2 = Partner.search([('ref', '=', 'ZEA-CLI-16')], limit=1)
        if not all([supplier, supplier2, customer, customer2]):
            raise UserError(_('Faltan contactos ficticios de Zeartex. Ejecute 1. Cargar catálogo seguro.'))
        for p, kind in [(supplier, 'liability_payable'), (supplier2, 'liability_payable'),
                        (customer, 'asset_receivable'), (customer2, 'asset_receivable')]:
            field = 'property_account_receivable_id' if kind == 'asset_receivable' else 'property_account_payable_id'
            acct = getattr(p.with_company(company), field, False)
            if not acct or acct.account_type != kind:
                raise UserError(_('Falta una cuenta de tercero válida para %s. No se publicó nada.') % p.display_name)

        # Este escenario NO contabiliza movimientos físicos ni costos en destino.
        # Por eso el costo comercial está etiquetado como gasto contable de prueba,
        # NO como existencias recibidas, ni como costo final AVCO del catálogo.
        def entry(suffix, date, items):
            debits = round(sum(d for _, _, d, _ in items), 2)
            credits = round(sum(c for _, _, _, c in items), 2)
            if abs(debits - credits) > 0.001:
                raise UserError(_('El asiento %s no está balanceado.') % suffix)
            mv = Move.create({'move_type': 'entry', 'company_id': company.id,
                'date': date, 'journal_id': general.id, 'ref': TAG + '-' + suffix,
                'line_ids': [(0, 0, {'name': label, 'account_id': acct.id, 'debit': debit, 'credit': credit})
                              for label, acct, debit, credit in items]})
            mv.action_post()
            return mv

        def invoice(suffix, date, kind, partner, jrnl, acct, amount, description):
            mv = Move.create({'company_id': company.id, 'journal_id': jrnl.id,
                'move_type': kind, 'partner_id': partner.id,
                'invoice_date': date, 'date': date, 'ref': TAG + '-' + suffix,
                'invoice_line_ids': [(0, 0, {'name': description, 'quantity': 1,
                    'price_unit': amount, 'account_id': acct.id, 'tax_ids': [(5, 0, 0)]})]})
            mv.action_post()
            return mv

        # La transacción de Odoo revierte íntegramente si hay una excepción.
        entry('01-CAPITAL', '2026-10-02', [
            ('Capital ficticio depositado', bank, 250000, 0),
            ('Aporte de capital DEMO', equity, 0, 250000)])
        entry('02-ADMIN', '2026-10-07', [
            ('Gastos administrativos comerciales DEMO', expense, 12000, 0),
            ('Pago de gastos DEMO por banco', bank, 0, 12000)])
        entry('03-LOGISTICA', '2026-10-09', [
            ('Gastos logísticos no capitalizados - simulación', expense, 5500, 0),
            ('Pago de logística DEMO por banco', bank, 0, 5500)])
        invoice('04-MERCADERIA', '2026-10-12', 'in_invoice', supplier,
                purchase_journal, direct, 42000,
                'Compra ficticia de mercadería contabilizada como costo DEMO, SIN recepción de inventario')
        invoice('05-SERVICIOS', '2026-10-15', 'in_invoice', supplier2,
                purchase_journal, expense, 9000,
                'Servicios comerciales ficticios SIN costos en destino ni valoración de inventario')
        invoice('06-VENTA-MAY', '2026-10-20', 'out_invoice', customer,
                sale_journal, sales, 90000,
                'Venta mayorista ficticia de artículos de cotillón SIN salida de inventario')
        invoice('07-VENTA-MIN', '2026-10-22', 'out_invoice', customer2,
                sale_journal, sales, 30000,
                'Venta minorista ficticia SIN salida de inventario')
        return self._action_open_posted_demo(company)

    def _action_open_posted_demo(self, company):
        moves = self.env['account.move'].with_company(company).sudo().search([
            ('company_id', '=', company.id), ('ref', 'like', TAG + '%')], order='date,id')
        if not moves:
            raise UserError(_('Zeartex no tiene asientos del escenario publicado en %s. Use 7. Publicar escenario CONTABLE de prueba.') % company.display_name)
        return {'type': 'ir.actions.act_window', 'name': _('Asientos publicados – Zeartex'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('id', 'in', moves.ids)],
                'context': {'search_default_posted': 0}}

    def action_open_posted_demo(self):
        self.ensure_one()
        return self._action_open_posted_demo(self._company())

    def action_open_financial_report(self):
        self.ensure_one()
        action = self.env.ref('esi_finanzas_v20.action_balance', raise_if_not_found=False)
        if not action:
            raise UserError(_('No se encontró el acceso a Balance del módulo esi_finanzas_v20. Instale o verifique ese módulo.'))
        return action.read()[0]

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
