# -*- coding: utf-8 -*-
"""Reportes de Familia Agrocons. No modifica el código de esi_finanzas_v20.
Los movimientos y saldos se leen de account.move.line; nunca se altera un asiento.
"""
from collections import defaultdict
from html import escape
from odoo import fields, models, _
from odoo.exceptions import UserError


class AgroconsFinancialPresentation(models.TransientModel):
    _inherit = 'esi.finance.report'

    esi_structured = fields.Boolean(
        string='Presentación contable detallada - Familia Agrocons', default=False,
        help='Muestra informes por cuenta y grupos, sin crear ni alterar movimientos.')

    def _use_agro_format(self):
        """Aplica el formato al menú original de Finanzas SOLO en la compañía
        que tiene un escenario contable Agrocons publicado. El código de
        esi_finanzas_v20 permanece sin modificaciones.
        """
        self.ensure_one()
        if self.esi_structured:
            return True
        if self.kind not in ('balance', 'profit', 'trial', 'ledger'):
            return False
        if self.analytic_id:
            return False  # No mostrar una distribución analítica incompleta
        return bool(self.env['account.move'].search_count([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('ref', 'like', 'AGC-CONT-DEMO-2026%'),
        ]))

    def _report_data(self):
        self.ensure_one()
        if not self._use_agro_format():
            return super()._report_data()
        # Otros informes (caja, flujo, vencimientos, analítico, impuestos y resumen)
        # utilizan la lógica original de ESI, sin cambios ni duplicación de cifras.
        if self.kind not in ('balance', 'profit', 'trial', 'ledger'):
            return super()._report_data()
        self.check_access('read')
        if self.company_id not in self.env.companies or self.date_from > self.date_to:
            raise UserError(_('Revise la compañía y las fechas del informe.'))
        companies = self.company_id._accessible_branches() if self.include_branches else self.company_id
        domain = [('company_id', 'in', companies.ids), ('date', '<=', self.date_to),
                  ('display_type', 'not in', ['line_section', 'line_note'])]
        domain.append(('parent_state', '=', 'posted') if self.posted_only else ('parent_state', '!=', 'cancel'))
        if self.account_ids:
            domain.append(('account_id', 'in', self.account_ids.ids))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.store_id and not self.include_branches:
            if 'esi_store_id' in self.env['account.move.line']._fields:
                domain.append(('esi_store_id', '=', self.store_id.id))
        lines = self.env['account.move.line'].with_company(self.company_id).search(domain, order='date,id', limit=100001)
        if len(lines) > 100000:
            raise UserError(_('Demasiados apuntes. Reduzca las fechas o las cuentas.'))
        company_currency = self.company_id.currency_id
        accounts = {}
        opening, debits, credits = defaultdict(float), defaultdict(float), defaultdict(float)
        grouped = defaultdict(list)
        for line in lines:
            aid = line.account_id.id
            accounts[aid] = line.account_id
            if line.date < self.date_from:
                opening[aid] += line.balance
            else:
                debits[aid] += line.debit
                credits[aid] += line.credit
                grouped[aid].append(line)
        balance = {i: opening[i] + debits[i] - credits[i] for i in accounts}
        sorted_ids = sorted(accounts, key=lambda i: accounts[i].code or '')
        title = '%s · %s · %s · %s' % (
            dict(self._fields['kind'].selection).get(self.kind, self.kind),
            self.company_id.display_name,
            ('Al %s' % self.date_to) if self.kind == 'balance' else ('%s a %s' % (self.date_from, self.date_to)),
            company_currency.name)
        rnd = company_currency.round
        if self.kind == 'trial':
            rows = [[accounts[i].code or '', accounts[i].name, rnd(opening[i]),
                     rnd(debits[i]), rnd(credits[i]), rnd(balance[i])] for i in sorted_ids]
            rows.append(['', 'TOTAL', rnd(sum(opening.values())), rnd(sum(debits.values())),
                         rnd(sum(credits.values())), rnd(sum(balance.values()))])
            return title, ['Código', 'Cuenta', 'Saldo inicial', 'Débito', 'Crédito', 'Saldo final'], rows
        if self.kind == 'ledger':
            rows = []
            for i in sorted_ids:
                acc = accounts[i]
                running = opening[i]
                rows.append([acc.code or '', acc.name, '', '', 'Saldo inicial', '', 0.0, 0.0, rnd(running)])
                for line in grouped[i]:
                    running += line.balance
                    rows.append([acc.code or '', acc.name, str(line.date),
                                 line.journal_id.code or '', line.move_id.name or '',
                                 line.partner_id.display_name or '', rnd(line.debit),
                                 rnd(line.credit), rnd(running)])
            return title, ['Código', 'Cuenta', 'Fecha', 'Diario', 'Asiento', 'Contacto', 'Débito', 'Crédito', 'Saldo'], rows
        rows = []
        headers = ['Código', 'Cuenta / título', 'Débito', 'Crédito', 'Monto']
        def section(label):
            rows.append(['', label.upper(), '', '', ''])
        def add_accounts(filterfunc, sign=1.0, period=False):
            amount = 0.0
            for i in sorted_ids:
                acc = accounts[i]
                if not filterfunc(acc.account_type):
                    continue
                dr = debits[i] if period else opening[i] + debits[i]
                cr = credits[i] if period else credits[i]
                value = rnd(sign * (dr - cr))
                if company_currency.is_zero(value):
                    continue
                rows.append([acc.code or '', acc.name, rnd(dr), rnd(cr), value])
                amount += value
            return rnd(amount)
        def subtotal(label, value):
            rows.append(['', label, '', '', rnd(value)])
        if self.kind == 'profit':
            section('Ingresos')
            income = add_accounts(lambda t: t in ('income','income_other'), -1, True)
            subtotal('TOTAL INGRESOS', income)
            section('Costo de ventas')
            cost = add_accounts(lambda t: t == 'expense_direct_cost', 1, True)
            subtotal('TOTAL COSTO DE VENTAS', cost)
            subtotal('UTILIDAD BRUTA', income-cost)
            section('Gastos operativos y depreciaciones')
            expenses = add_accounts(lambda t: t in ('expense','expense_depreciation','expense_other'), 1, True)
            subtotal('TOTAL GASTOS', expenses)
            subtotal('RESULTADO DEL PERÍODO', income-cost-expenses)
            return title, headers, rows
        section('Activo')
        section('Activo corriente')
        ac = add_accounts(lambda t: t.startswith('asset') and t not in ('asset_fixed','asset_non_current'))
        subtotal('TOTAL ACTIVO CORRIENTE', ac)
        section('Activo no corriente')
        anc = add_accounts(lambda t: t in ('asset_fixed','asset_non_current'))
        subtotal('TOTAL ACTIVO NO CORRIENTE', anc)
        subtotal('TOTAL ACTIVO', ac+anc)
        section('Pasivo')
        section('Pasivo corriente')
        pc = add_accounts(lambda t: t.startswith('liability') and t != 'liability_non_current', -1)
        subtotal('TOTAL PASIVO CORRIENTE', pc)
        section('Pasivo no corriente')
        pnc = add_accounts(lambda t: t == 'liability_non_current', -1)
        subtotal('TOTAL PASIVO NO CORRIENTE', pnc)
        subtotal('TOTAL PASIVO', pc+pnc)
        section('Patrimonio')
        equity = add_accounts(lambda t: t.startswith('equity'), -1)
        pl = -sum(balance[i] for i in sorted_ids if accounts[i].account_type.startswith(('income','expense')))
        if not company_currency.is_zero(pl):
            rows.append(['', 'Resultado acumulado pendiente de cierre', '', '', rnd(pl)])
        subtotal('TOTAL PATRIMONIO', equity+pl)
        subtotal('TOTAL PASIVO Y PATRIMONIO', pc+pnc+equity+pl)
        subtotal('DIFERENCIA DE CUADRE', ac+anc-pc-pnc-equity-pl)
        return title, headers, rows

    def _html(self, title, headers, rows):
        self.ensure_one()
        if not self._use_agro_format():
            return super()._html(title, headers, rows)
        e = lambda val: escape(str(val if val is not None else ''))
        chunks = ['<div style="font-family:Arial,sans-serif">',
                  '<h2 style="text-align:center;color:#072955">%s</h2>' % e(title),
                  '<p style="text-align:center">Expresado en %s</p>' % e(self.company_id.currency_id.name),
                  '<table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr>']
        for header in headers:
            chunks.append('<th style="background:#072955;color:white;padding:7px;border:1px solid #ddd">%s</th>' % e(header))
        chunks.append('</tr></thead><tbody>')
        for values in rows:
            heading = len(values) == 5 and values[0] == '' and values[2] == '' and values[3] == ''
            total = (values[1] or '').upper().startswith(('TOTAL','UTILIDAD','RESULTADO','DIFERENCIA'))
            bg = '#e6edf4' if heading else ('#f5f7f8' if total else 'white')
            chunks.append('<tr style="background:%s;font-weight:%s">' % (bg, 'bold' if heading or total else 'normal'))
            for val in values:
                form = '{:,.2f}'.format(val) if isinstance(val,(float,int)) else e(val)
                chunks.append('<td style="border:1px solid #ddd;padding:6px;text-align:%s">%s</td>' %
                              ('right' if isinstance(val,(float,int)) else 'left', form))
            chunks.append('</tr>')
        chunks.append('</tbody></table></div>')
        return ''.join(chunks)
