# -*- coding: utf-8 -*-
"""Presentación agrupada de informes ESI sin alterar asientos publicados.
Solo se activa al seleccionar la opción de presentación estructurada del informe.
"""
from collections import defaultdict
from html import escape
from odoo import fields, models, _
from odoo.exceptions import UserError


class ZeartexStructuredFinancialReport(models.TransientModel):
    _inherit = 'esi.finance.report'

    esi_structured = fields.Boolean(
        string='Presentación estructurada (Activo, Pasivo, Patrimonio y Resultados)',
        default=False,
        help='Agrupa cuentas y subtotales a partir de apuntes contables; no crea ni modifica asientos.')

    def _html(self, title, headers, rows):
        if not self.esi_structured or self.kind not in ('balance', 'profit'):
            return super()._html(title, headers, rows)
        esc = lambda x: escape(str(x if x is not None else ''))
        header = ''.join('<th style="background:#072955;color:white;padding:8px;text-align:left">%s</th>' % esc(h) for h in headers)
        body = []
        for code, name, typ, value in rows:
            is_section = typ == 'Sección'
            is_total = typ == 'Subtotal / Total'
            bg = '#e7edf2' if is_section else '#f2f5f7' if is_total else '#ffffff'
            weight = 'bold' if is_section or is_total else 'normal'
            amount = '' if is_section else ('{:,.2f}'.format(float(value)))
            cells = (code, name, '' if is_section else typ, amount)
            body.append('<tr style="background:%s;font-weight:%s">%s</tr>' % (
                bg, weight, ''.join('<td style="padding:6px;border-bottom:1px solid #ddd">%s</td>' % esc(c) for c in cells)))
        return '<h3>%s</h3><table style="width:100%%;border-collapse:collapse"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (esc(title), header, ''.join(body))

    def _report_data(self):
        self.ensure_one()
        if not self.esi_structured or self.kind not in ('balance', 'profit'):
            return super()._report_data()
        if self.company_id not in self.env.companies or self.date_from > self.date_to:
            raise UserError(_('Revise compañía y rango de fechas.'))
        if self.analytic_id or self.partner_id or self.account_ids or self.store_id:
            raise UserError(_('Para el estado financiero completo, deje vacíos los filtros de cuenta, contacto, analítica y sucursal.'))
        companies = self.company_id._accessible_branches() if self.include_branches else self.company_id
        domain = [
            ('company_id', 'in', companies.ids),
            ('date', '<=', self.date_to),
            ('display_type', 'not in', ['line_section', 'line_note']),
            ('parent_state', '=', 'posted' if self.posted_only else 'draft'),
        ]
        if not self.posted_only:
            domain[-1] = ('parent_state', '!=', 'cancel')
        entries = self.env['account.move.line'].with_company(self.company_id).search(domain, order='account_id, date, id', limit=100001)
        if len(entries) > 100000:
            raise UserError(_('El informe supera los 100.000 apuntes. Reduzca el período o consulte los informes estándar.'))
        balances = defaultdict(float)
        results_period = defaultdict(float)
        names = {}
        for line in entries:
            account = line.account_id
            names[account.id] = account
            balances[account.id] += line.balance
            if self.date_from <= line.date <= self.date_to:
                results_period[account.id] += line.balance

        title = '%s · %s · %s · %s' % (
            'Balance general' if self.kind == 'balance' else 'Estado de resultados',
            self.company_id.display_name,
            'al %s' % self.date_to if self.kind == 'balance' else '%s a %s' % (self.date_from, self.date_to),
            self.company_id.currency_id.name)
        # La advertencia se muestra una sola vez, NO en cada movimiento o producto.
        title += ' · Presentación financiera de datos registrados'
        headers = ['Código', 'Cuenta / agrupación', 'Clasificación', 'Importe']
        rows = []
        currency = self.company_id.currency_id

        def section(name):
            rows.append(['', name.upper(), 'Sección', 0.0])

        def total(name, amount):
            rows.append(['', name, 'Subtotal / Total', currency.round(amount)])

        def account_name(account):
            # Solo en la visualización: no cambia nombres ni asientos contables.
            name = account.name
            if account.code == '519901' and 'Zeartex' in name:
                return 'Costo de mercaderías vendidas'
            return name

        def add_accounts(account_ids, source, sign=1):
            amount = 0.0
            for aid in sorted(account_ids, key=lambda i: names[i].code or ''):
                value = currency.round(sign * source[aid])
                if currency.is_zero(value):
                    continue
                account = names[aid]
                rows.append([account.code or '', account_name(account), account.account_type, value])
                amount += value
            return currency.round(amount)

        if self.kind == 'profit':
            typ = lambda aid: names[aid].account_type
            income = [i for i in names if typ(i) in ('income', 'income_other')]
            cost = [i for i in names if typ(i) == 'expense_direct_cost']
            operating = [i for i in names if typ(i) in ('expense', 'expense_depreciation', 'expense_other')]
            section('Ingresos operativos y otros ingresos')
            revenue = add_accounts(income, results_period, -1)
            total('TOTAL INGRESOS', revenue)
            section('Costo de ventas')
            cogs = add_accounts(cost, results_period, 1)
            total('TOTAL COSTO DE VENTAS', cogs)
            gross = currency.round(revenue-cogs)
            total('UTILIDAD BRUTA', gross)
            section('Gastos de operación y otros gastos')
            expenses = add_accounts(operating, results_period, 1)
            total('TOTAL GASTOS', expenses)
            total('RESULTADO DEL PERÍODO (antes de ajustes e impuestos no registrados)', gross-expenses)
            return title, headers, rows

        typ = lambda aid: names[aid].account_type
        assets = [i for i in names if typ(i).startswith('asset')]
        liabilities = [i for i in names if typ(i).startswith('liability')]
        equity = [i for i in names if typ(i).startswith('equity')]
        income = [i for i in names if typ(i).startswith('income')]
        expenses = [i for i in names if typ(i).startswith('expense')]
        current_assets = [i for i in assets if typ(i) not in ('asset_fixed', 'asset_non_current')]
        fixed_assets = [i for i in assets if typ(i) in ('asset_fixed', 'asset_non_current')]
        short_liab = [i for i in liabilities if typ(i) not in ('liability_non_current',)]
        long_liab = [i for i in liabilities if typ(i) == 'liability_non_current']
        section('ACTIVO')
        section('Activo corriente')
        ac = add_accounts(current_assets, balances)
        total('TOTAL ACTIVO CORRIENTE', ac)
        section('Activo no corriente')
        anc = add_accounts(fixed_assets, balances)
        total('TOTAL ACTIVO NO CORRIENTE', anc)
        total('TOTAL ACTIVO', ac+anc)
        section('PASIVO')
        section('Pasivo corriente')
        pc = add_accounts(short_liab, balances, -1)
        total('TOTAL PASIVO CORRIENTE', pc)
        section('Pasivo no corriente')
        pnc = add_accounts(long_liab, balances, -1)
        total('TOTAL PASIVO NO CORRIENTE', pnc)
        total('TOTAL PASIVO', pc+pnc)
        section('PATRIMONIO')
        eq = add_accounts(equity, balances, -1)
        earnings = currency.round(-sum(balances[i] for i in income + expenses))
        if not currency.is_zero(earnings):
            rows.append(['', 'Resultado acumulado sin cierre contable', 'Resultado', earnings])
        total('TOTAL PATRIMONIO (incluye resultado sin cierre)', eq+earnings)
        total('TOTAL PASIVO Y PATRIMONIO', pc+pnc+eq+earnings)
        diff = currency.round(ac+anc-pc-pnc-eq-earnings)
        total('DIFERENCIA DE CUADRE (debe ser cero)', diff)
        return title, headers, rows
