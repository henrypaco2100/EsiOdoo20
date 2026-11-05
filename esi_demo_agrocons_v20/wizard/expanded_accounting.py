# -*- coding: utf-8 -*-
"""Optional demonstration-only journal history. Never changes physical inventory or AVCO.
Only for an isolated test database, with two explicit approvals.
"""
from odoo import models, _
from odoo.exceptions import UserError


class AgroconsExpandedAccounting(models.TransientModel):
    _inherit = 'esi.agro.demo.wizard'

    def action_load_extended_accounting(self):
        self.ensure_one()
        if not self.confirmation or not self.confirm_posted_demo:
            raise UserError(_('Confirme base aislada de pruebas y autorización contable.'))
        company = self.company_id
        if company not in self.env.companies:
            raise UserError(_('Active la compañía seleccionada en el selector superior.'))
        env = self.with_company(company).env
        Account = env['account.account'].sudo()
        Move = env['account.move'].sudo()
        prefix = 'AGC-AMPLIACION-2026-'
        if Move.search_count([('company_id', '=', company.id), ('ref', '=like', prefix + '%')]):
            return self._open_extended_entries(company)
        journal = env['account.journal'].sudo().search([
            ('company_id', '=', company.id), ('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_('Configure un diario de operaciones diversas para la compañía.'))
        specs = {
            'bank': ('119920', 'Banco – operaciones agrícolas', 'asset_cash'),
            'capital': ('319920', 'Aportes de capital', 'equity'),
            'loan': ('219920', 'Préstamos agrícolas a largo plazo', 'liability_non_current'),
            'equip': ('129920', 'Maquinaria agrícola', 'asset_fixed'),
            'vehicle': ('129921', 'Vehículos de distribución', 'asset_fixed'),
            'tools': ('129922', 'Herramientas y equipos agrícolas', 'asset_fixed'),
            'depr': ('129923', 'Depreciación acumulada maquinaria', 'asset_fixed'),
            'depr_exp': ('629920', 'Depreciación de maquinaria', 'expense_depreciation'),
            'fuel': ('529920', 'Combustibles y lubricantes', 'expense'),
            'labor': ('529921', 'Servicios y mano de obra agrícola', 'expense_direct_cost'),
            'maintenance': ('529922', 'Mantenimiento de maquinaria', 'expense'),
            'rent': ('539920', 'Alquiler de instalaciones', 'expense'),
            'electric': ('539921', 'Energía y servicios básicos', 'expense'),
            'transport': ('529923', 'Transporte de la producción', 'expense_direct_cost'),
            'interest': ('639920', 'Intereses bancarios', 'expense'),
            'services': ('429920', 'Ingresos por servicios agrícolas', 'income'),
            'payable': ('219921', 'Obligaciones comerciales agrícolas', 'liability_current'),
        }
        found = {}
        for key, (code, label, kind) in specs.items():
            domain = [('code', '=', code)]
            if 'company_ids' in Account._fields:
                domain.append(('company_ids', 'in', [company.id]))
            elif 'company_id' in Account._fields:
                domain.append(('company_id', '=', company.id))
            acc = Account.search(domain, limit=1)
            if acc and (acc.name != label or acc.account_type != kind):
                raise UserError(_('La cuenta %s ya existe con otro nombre/tipo. Revísela primero.') % code)
            if not acc:
                vals = {'code': code, 'name': label, 'account_type': kind}
                if 'company_ids' in Account._fields:
                    vals['company_ids'] = [(6, 0, [company.id])]
                elif 'company_id' in Account._fields:
                    vals['company_id'] = company.id
                acc = Account.create(vals)
            found[key] = acc

        transactions = [
            ('01-CAPITAL','2026-10-01','Aporte de capital a cuenta bancaria', [('bank',300000,0),('capital',0,300000)]),
            ('02-PRESTAMO','2026-10-03','Crédito bancario para campaña', [('bank',120000,0),('loan',0,120000)]),
            ('03-MAQUINARIA','2026-10-04','Adquisición de sembradora', [('equip',45000,0),('bank',0,45000)]),
            ('04-VEHICULO','2026-10-05','Adquisición de vehículo agrícola', [('vehicle',60000,0),('bank',0,60000)]),
            ('05-HERRAMIENTAS','2026-10-06','Compra de herramientas', [('tools',15000,0),('bank',0,15000)]),
            ('06-COMBUSTIBLE','2026-10-10','Consumo de combustible registrado contablemente', [('fuel',7000,0),('bank',0,7000)]),
            ('07-LABORES','2026-10-12','Servicio de preparación de suelo', [('labor',9000,0),('bank',0,9000)]),
            ('08-MANTENIMIENTO','2026-10-14','Servicio de mantenimiento pendiente de pago', [('maintenance',5000,0),('payable',0,5000)]),
            ('09-ALQUILER','2026-10-16','Alquiler de depósito agrícola', [('rent',3500,0),('bank',0,3500)]),
            ('10-SERVICIOS','2026-10-18','Servicios básicos', [('electric',2500,0),('bank',0,2500)]),
            ('11-TRANSPORTE','2026-10-19','Transporte de producción', [('transport',4000,0),('bank',0,4000)]),
            ('12-VENTA-SERVICIO','2026-10-22','Servicio agrícola cobrado', [('bank',25000,0),('services',0,25000)]),
            ('13-INTERESES','2026-10-24','Intereses bancarios', [('interest',1000,0),('bank',0,1000)]),
            ('14-DEPRECIACION','2026-10-28','Depreciación mensual maquinaria', [('depr_exp',5000,0),('depr',0,5000)]),
        ]
        for suffix, date, description, values in transactions:
            ref = prefix + suffix
            if Move.search([('company_id', '=', company.id), ('ref', '=', ref)], limit=1):
                continue
            dr = round(sum(x[1] for x in values),2)
            cr = round(sum(x[2] for x in values),2)
            if dr != cr:
                raise UserError(_('Asiento sin cuadrar: %s') % ref)
            move = Move.create({
                'company_id': company.id, 'move_type': 'entry', 'journal_id': journal.id,
                'date': date, 'ref': ref,
                'line_ids': [(0, 0, {'name': description, 'account_id': found[key].id,
                                     'debit': debit, 'credit': credit})
                              for key, debit, credit in values],
            })
            move.action_post()
        return self._open_extended_entries(company)

    def _open_extended_entries(self, company):
        return {
            'type': 'ir.actions.act_window', 'name': _('Movimientos contables agrícolas – ejemplo'),
            'res_model': 'account.move', 'view_mode': 'list,form',
            'domain': [('company_id', '=', company.id),
                       ('ref', '=like', 'AGC-AMPLIACION-2026-%')],
        }
