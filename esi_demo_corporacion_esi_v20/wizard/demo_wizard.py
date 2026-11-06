# -*- coding: utf-8 -*-
from odoo import Command, fields, models, _
from odoo.exceptions import UserError


# -----------------------------------------------------------------------------
# FUENTE CONTABLE
# -----------------------------------------------------------------------------
# Los importes proceden de los PDF entregados por el usuario. Solo se registran
# cuentas de movimiento (hojas) y se crean tambien las cuentas padre para que el
# plan mantenga la estructura de la fuente.

ACCOUNT_SPECS = [
    # code, name, type, parent
# Odoo 20 no permite compartir cuentas de tipo asset_cash entre varias companias.
# Como esta demo usa un unico plan compartido entre matriz y sucursales, las cuentas
# Caja/Bancos del plan fuente se clasifican como asset_current, conservando codigo,
# nombre y saldo. Los diarios por sucursal siguen siendo independientes.
    ('1', 'ACTIVO', 'asset_current', False),
    ('11', 'ACTIVO CORRIENTE', 'asset_current', '1'),
    ('111', 'DISPONIBLE', 'asset_current', '11'),
    ('11101', 'CAJA', 'asset_current', '111'),
    ('1110101', 'CAJA GENERAL', 'asset_current', '11101'),
    ('1110102', 'CAJA CHICA', 'asset_current', '11101'),
    ('11102', 'BANCOS', 'asset_current', '111'),
    ('1110201', 'BANCO MONEDA NACIONAL', 'asset_current', '11102'),
    ('1110202', 'BANCO MONEDA EXTRANJERA', 'asset_current', '11102'),
    ('112', 'EXIGIBLE / CUENTAS POR COBRAR', 'asset_current', '11'),
    ('1120101', 'CLIENTES POR COBRAR', 'asset_receivable', '112'),
    ('1120201', 'ANTICIPOS A PROVEEDORES', 'asset_prepayments', '112'),
    ('1120301', 'CREDITO FISCAL IVA', 'asset_current', '112'),
    ('113', 'REALIZABLE / INVENTARIOS', 'asset_current', '11'),
    ('1130101', 'INVENTARIO DE SEMILLAS', 'asset_current', '113'),
    ('1130102', 'INVENTARIO DE FERTILIZANTES', 'asset_current', '113'),
    ('1130103', 'INVENTARIO DE AGROQUIMICOS', 'asset_current', '113'),
    ('1130104', 'INVENTARIO DE REPUESTOS Y MATERIALES', 'asset_current', '113'),
    ('1130105', 'INVENTARIO DE PRODUCCION AGRICOLA', 'asset_current', '113'),
    ('114', 'OTROS ACTIVOS CORRIENTES', 'asset_current', '11'),
    ('1140101', 'PAGOS ANTICIPADOS', 'asset_prepayments', '114'),
    ('12', 'ACTIVO NO CORRIENTE', 'asset_non_current', '1'),
    ('121', 'ACTIVOS FIJOS', 'asset_fixed', '12'),
    ('1210101', 'TERRENOS', 'asset_fixed', '121'),
    ('1210201', 'MAQUINARIA AGRICOLA', 'asset_fixed', '121'),
    ('1210301', 'VEHICULOS', 'asset_fixed', '121'),
    ('1210401', 'EQUIPOS Y HERRAMIENTAS', 'asset_fixed', '121'),
    ('1210501', 'MUEBLES Y ENSERES', 'asset_fixed', '121'),
    ('129', 'DEPRECIACION ACUMULADA', 'asset_fixed', '12'),
    ('12901', 'DEPRECIACION ACUMULADA MAQUINARIA', 'asset_fixed', '129'),
    ('12902', 'DEPRECIACION ACUMULADA VEHICULOS', 'asset_fixed', '129'),

    ('2', 'PASIVO', 'liability_current', False),
    ('21', 'PASIVO CORRIENTE', 'liability_current', '2'),
    ('211', 'OBLIGACIONES A CORTO PLAZO', 'liability_current', '21'),
    ('2110101', 'PROVEEDORES POR PAGAR', 'liability_payable', '211'),
    ('2110102', 'OTRAS CUENTAS POR PAGAR', 'liability_current', '211'),
    ('2110201', 'SUELDOS POR PAGAR', 'liability_current', '211'),
    ('2110202', 'APORTES Y RETENCIONES POR PAGAR', 'liability_current', '211'),
    ('2110301', 'DEBITO FISCAL IVA', 'liability_current', '211'),
    ('2110302', 'IMPUESTOS POR PAGAR', 'liability_current', '211'),
    ('22', 'PASIVO NO CORRIENTE', 'liability_non_current', '2'),
    ('221', 'OBLIGACIONES A LARGO PLAZO', 'liability_non_current', '22'),
    ('2210101', 'PRESTAMOS BANCARIOS', 'liability_non_current', '221'),

    ('3', 'PATRIMONIO', 'equity', False),
    ('31', 'CAPITAL', 'equity', '3'),
    ('3110101', 'CAPITAL SOCIAL', 'equity', '31'),
    ('3110102', 'APORTES DE SOCIOS', 'equity', '31'),
    ('32', 'RESULTADOS ACUMULADOS', 'equity', '3'),
    ('3210101', 'RESULTADOS ACUMULADOS', 'equity', '32'),
    ('399998', 'DIFERENCIA DOCUMENTAL BALANCE GENERAL POR CONCILIAR', 'equity', '3'),
    ('399999', 'CONTRAPARTIDA TECNICA SALDOS ESTADO DE RESULTADO', 'equity', '3'),

    ('4', 'INGRESOS', 'income', False),
    ('41', 'INGRESOS OPERATIVOS', 'income', '4'),
    ('411', 'INGRESOS POR VENTA DE PRODUCTOS', 'income', '41'),
    ('4110101', 'VENTA DE SEMILLAS', 'income', '411'),
    ('4110102', 'VENTA DE GRANOS', 'income', '411'),
    ('4110103', 'VENTA DE FERTILIZANTES', 'income', '411'),
    ('4110104', 'VENTA DE AGROQUIMICOS', 'income', '411'),
    ('4110105', 'VENTA DE REPUESTOS Y MATERIALES', 'income', '411'),
    ('412', 'INGRESOS POR SERVICIOS', 'income', '41'),
    ('4120101', 'SERVICIOS DE PREPARACION DE SUELO', 'income', '412'),
    ('4120102', 'SERVICIOS DE SIEMBRA Y COSECHA', 'income', '412'),
    ('4120103', 'SERVICIOS DE TRANSPORTE AGRICOLA', 'income', '412'),
    ('49', 'OTROS INGRESOS', 'income_other', '4'),
    ('4910101', 'OTROS INGRESOS', 'income_other', '49'),

    ('5', 'COSTOS', 'expense_direct_cost', False),
    ('51', 'COSTO DE VENTAS', 'expense_direct_cost', '5'),
    ('5110101', 'COSTO DE SEMILLAS VENDIDAS', 'expense_direct_cost', '51'),
    ('5110102', 'COSTO DE GRANOS VENDIDOS', 'expense_direct_cost', '51'),
    ('5110103', 'COSTO DE FERTILIZANTES VENDIDOS', 'expense_direct_cost', '51'),
    ('5110104', 'COSTO DE AGROQUIMICOS VENDIDOS', 'expense_direct_cost', '51'),
    # Cuenta faltante para poder contabilizar automaticamente la categoria de repuestos/materiales.
    ('5110105', 'COSTO DE REPUESTOS Y MATERIALES VENDIDOS', 'expense_direct_cost', '51'),
    ('52', 'COSTOS DE PRODUCCION AGRICOLA', 'expense_direct_cost', '5'),
    ('5210101', 'MANO DE OBRA AGRICOLA', 'expense_direct_cost', '52'),
    ('5210102', 'COMBUSTIBLE Y LUBRICANTES', 'expense_direct_cost', '52'),
    ('5210103', 'MANTENIMIENTO DE MAQUINARIA', 'expense_direct_cost', '52'),
    ('5210104', 'FERTILIZANTES CONSUMIDOS', 'expense_direct_cost', '52'),
    ('5210105', 'AGROQUIMICOS CONSUMIDOS', 'expense_direct_cost', '52'),
    ('5210106', 'SEMILLAS CONSUMIDAS EN PRODUCCION', 'expense_direct_cost', '52'),
    ('5210107', 'FLETES Y TRANSPORTE DE PRODUCCION', 'expense_direct_cost', '52'),

    ('6', 'GASTOS', 'expense', False),
    ('61', 'GASTOS DE ADMINISTRACION', 'expense', '6'),
    ('6110101', 'SUELDOS ADMINISTRATIVOS', 'expense', '61'),
    ('6110102', 'SERVICIOS BASICOS', 'expense', '61'),
    ('6110103', 'INTERNET Y TELEFONIA', 'expense', '61'),
    ('6110104', 'ALQUILERES', 'expense', '61'),
    ('6110105', 'MATERIAL DE OFICINA', 'expense', '61'),
    ('6110106', 'SERVICIOS DE LIMPIEZA', 'expense', '61'),
    ('6110107', 'HONORARIOS PROFESIONALES', 'expense', '61'),
    ('6110108', 'GASTOS BANCARIOS', 'expense', '61'),
    ('6110109', 'PUBLICIDAD Y PROMOCION', 'expense', '61'),
    ('6110110', 'VIATICOS Y MOVILIDAD', 'expense', '61'),
    ('62', 'DEPRECIACIONES', 'expense_depreciation', '6'),
    ('6210101', 'DEPRECIACION DE MAQUINARIA', 'expense_depreciation', '62'),
    ('6210102', 'DEPRECIACION DE VEHICULOS', 'expense_depreciation', '62'),
    ('69', 'OTROS GASTOS', 'expense_other', '6'),
    ('6910101', 'OTROS GASTOS', 'expense_other', '69'),
]

# code, amount, side.  d = debe, c = haber
SOURCE_BALANCE_LINES = [
    ('1110101', 43000.00, 'd'), ('1110102', 8700.00, 'd'),
    ('1110201', 535000.00, 'd'), ('1110202', 146100.00, 'd'),
    ('1120101', 347000.00, 'd'), ('1120201', 37000.00, 'd'), ('1120301', 63000.00, 'd'),
    ('1130101', 415000.00, 'd'), ('1130102', 223000.00, 'd'), ('1130103', 163000.00, 'd'),
    ('1130104', 86000.00, 'd'), ('1130105', 299000.00, 'd'), ('1140101', 30000.00, 'd'),
    ('1210101', 970000.00, 'd'), ('1210201', 1330000.00, 'd'), ('1210301', 575000.00, 'd'),
    ('1210401', 181000.00, 'd'), ('1210501', 103000.00, 'd'),
    ('12901', 213000.00, 'c'), ('12902', 120000.00, 'c'),
    ('2110101', 533500.00, 'c'), ('2110102', 98000.00, 'c'), ('2110201', 42500.00, 'c'),
    ('2110202', 22000.00, 'c'), ('2110301', 71000.00, 'c'), ('2110302', 64000.00, 'c'),
    ('2210101', 835000.00, 'c'), ('3110101', 2600000.00, 'c'), ('3110102', 550000.00, 'c'),
    ('3210101', 406300.00, 'c'),
]

SOURCE_PROFIT_LINES = [
    ('4110101', 837000.00, 'c'), ('4110102', 574000.00, 'c'), ('4110103', 335000.00, 'c'),
    ('4110104', 215000.00, 'c'), ('4110105', 72000.00, 'c'),
    ('4120101', 138000.00, 'c'), ('4120102', 167000.00, 'c'), ('4120103', 92000.00, 'c'),
    ('4910101', 26000.00, 'c'),
    ('5110101', 418000.00, 'd'), ('5110102', 279000.00, 'd'),
    ('5110103', 167000.00, 'd'), ('5110104', 99000.00, 'd'),
    ('5210101', 132000.00, 'd'), ('5210102', 84000.00, 'd'), ('5210103', 55000.00, 'd'),
    ('5210104', 71000.00, 'd'), ('5210105', 46000.00, 'd'), ('5210106', 76000.00, 'd'),
    ('5210107', 41000.00, 'd'),
    ('6110101', 115000.00, 'd'), ('6110102', 21000.00, 'd'), ('6110103', 13200.00, 'd'),
    ('6110104', 51000.00, 'd'), ('6110105', 11200.00, 'd'), ('6110106', 14200.00, 'd'),
    ('6110107', 26500.00, 'd'), ('6110108', 7200.00, 'd'), ('6110109', 18500.00, 'd'),
    ('6110110', 15500.00, 'd'), ('6210101', 33000.00, 'd'), ('6210102', 22500.00, 'd'),
    ('6910101', 18500.00, 'd'),
]

# El propio documento fuente tiene Activo 5.221.800 y Pasivo+Patrimonio 5.222.300.
SOURCE_BALANCE_DOCUMENT_DIFFERENCE = 500.00
SOURCE_PROFIT_RESULT = 620700.00

CATEGORY_SPECS = [
    # key, name, valuation account, income, expense/cost
    ('seeds', 'ESI DEMO | Semillas', '1130101', '4110101', '5110101'),
    ('fertilizers', 'ESI DEMO | Fertilizantes', '1130102', '4110103', '5110103'),
    ('agrochemicals', 'ESI DEMO | Agroquimicos', '1130103', '4110104', '5110104'),
    ('materials', 'ESI DEMO | Repuestos y materiales', '1130104', '4110105', '5110105'),
    ('harvest', 'ESI DEMO | Produccion agricola', '1130105', '4110102', '5110102'),
]

PRODUCT_SPECS = [
    # 15 insumos para la siembra/operacion de soya
    ('SOY-SEM-001', 'Semilla de soya certificada', 'seeds', 'kg', 12.00, 15.50, False, True),
    ('SOY-INO-001', 'Inoculante Bradyrhizobium para soya', 'agrochemicals', 'unit', 45.00, 58.00, False, True),
    ('SOY-TRT-001', 'Tratamiento fungicida para semilla de soya', 'agrochemicals', 'l', 92.00, 118.00, False, True),
    ('SOY-FER-001', 'Fertilizante MAP 11-52-0', 'fertilizers', 'kg', 8.40, 10.90, False, True),
    ('SOY-FER-002', 'Fertilizante DAP 18-46-0', 'fertilizers', 'kg', 8.10, 10.50, False, True),
    ('SOY-FER-003', 'Cloruro de potasio KCl', 'fertilizers', 'kg', 6.80, 8.80, False, True),
    ('SOY-FER-004', 'Urea granulada 46-0-0', 'fertilizers', 'kg', 6.20, 8.10, False, True),
    ('SOY-HER-001', 'Herbicida Glifosato', 'agrochemicals', 'l', 65.00, 84.50, False, True),
    ('SOY-HER-002', 'Herbicida S-Metolacloro', 'agrochemicals', 'l', 78.00, 101.00, False, True),
    ('SOY-HER-003', 'Herbicida Cletodim', 'agrochemicals', 'l', 88.00, 114.00, False, True),
    ('SOY-INS-001', 'Insecticida Lambda-cihalotrina', 'agrochemicals', 'l', 72.00, 94.00, False, True),
    ('SOY-FUN-001', 'Fungicida Azoxistrobina + Ciproconazol', 'agrochemicals', 'l', 96.00, 125.00, False, True),
    ('SOY-MIC-001', 'Micronutriente foliar Boro-Zinc', 'fertilizers', 'l', 54.00, 70.00, False, True),
    ('SOY-COA-001', 'Coadyuvante agricola', 'agrochemicals', 'l', 38.00, 49.00, False, True),
    ('SOY-COM-001', 'Diesel agricola', 'materials', 'l', 7.20, 8.50, False, True),
    # 3 productos cosechados
    ('SOY-GRA-001', 'Soya grano comercial', 'harvest', 'kg', 2.50, 3.20, True, False),
    ('SOY-GRA-002', 'Soya semilla seleccionada cosechada', 'harvest', 'kg', 3.10, 4.20, True, False),
    ('SOY-GRA-003', 'Soya grano segunda / descarte', 'harvest', 'kg', 1.80, 2.30, True, False),
    # 2 productos de apoyo para completar un catalogo de 20
    ('SOY-REP-001', 'Filtro de aceite para tractor', 'materials', 'unit', 125.00, 165.00, False, True),
    ('SOY-REP-002', 'Grasa multiproposito agricola', 'materials', 'unit', 48.00, 62.00, False, True),
]


class EsiCorporacionDemoWizard(models.TransientModel):
    _name = 'esi.corporacion.demo.wizard'
    _description = 'Carga Demo Corporacion ESI multisucursal'

    balance_date = fields.Date(
        string='Fecha para cargar saldos fuente',
        required=True,
        default=fields.Date.today,
        help='Los PDF entregados no muestran una fecha de corte visible. Seleccione aqui la fecha contable que desea usar.',
    )
    create_draft_flow = fields.Boolean(
        string='Crear flujo basico en borrador por sucursal',
        default=True,
        help='Crea una RFQ y una cotizacion por sucursal. No confirma recepciones, entregas, facturas ni stock.',
    )
    confirmation = fields.Boolean(string='Confirmo que esta es una base nueva / de demostracion')
    result_summary = fields.Text(string='Resumen')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _bob_currency(self):
        currency = self.env.ref('base.BOB', raise_if_not_found=False)
        return currency or self.env['res.currency'].sudo().search([('name', '=', 'BOB')], limit=1)

    def _bolivia(self):
        return self.env.ref('base.bo', raise_if_not_found=False) or self.env['res.country'].sudo().search([('code', '=', 'BO')], limit=1)

    def _ensure_companies(self):
        Company = self.env['res.company'].sudo()
        bob = self._bob_currency()
        if not bob:
            raise UserError(_('No se encontro la moneda BOB. Active Boliviano antes de cargar la demo.'))
        bolivia = self._bolivia()

        root = Company.search([('name', '=', 'CORPORACION ESI'), ('parent_id', '=', False)], limit=1)
        if not root:
            root = self.env.company.sudo()
            # El wizard se declara para una base nueva: reutilizamos la compania inicial
            # para no dejar una "My Company" huerfana.
            vals = {'name': 'CORPORACION ESI', 'currency_id': bob.id}
            if bolivia:
                vals['country_id'] = bolivia.id
            root.write(vals)
        else:
            vals = {'currency_id': bob.id}
            if bolivia:
                vals['country_id'] = bolivia.id
            root.write(vals)

        branches = {}
        for key, name in (
            ('central', 'SUCURSAL CENTRAL'),
            ('scz', 'SUCURSAL SCZ'),
            ('cbba', 'SUCURSAL CBBA'),
        ):
            branch = Company.search([('name', '=', name), ('parent_id', '=', root.id)], limit=1)
            if not branch:
                vals = {'name': name, 'parent_id': root.id, 'currency_id': bob.id}
                if bolivia:
                    vals['country_id'] = bolivia.id
                branch = Company.create(vals)
            branches[key] = branch

        companies = root | branches['central'] | branches['scz'] | branches['cbba']
        # Dar acceso al administrador que ejecuta el wizard.
        self.env.user.sudo().write({'company_ids': [Command.link(c.id) for c in companies]})
        return root, branches, companies

    def _find_shared_account(self, root, code):
        Account = self.env['account.account'].sudo().with_company(root).with_context(allowed_company_ids=[root.id])
        return Account.search([('code', '=', code)], limit=1)

    def _ensure_accounts(self, root, companies):
        Account = self.env['account.account'].sudo().with_company(root).with_context(allowed_company_ids=companies.ids)
        accounts = {}
        existing_move_lines = self.env['account.move.line'].sudo()

        # Primera pasada: crear / alinear cuentas sin padres.
        for code, name, account_type, _parent_code in ACCOUNT_SPECS:
            acc = self._find_shared_account(root, code)
            vals = {
                'name': name,
                'account_type': account_type,
                'company_ids': [Command.set(companies.ids)],
            }
            if account_type in ('asset_receivable', 'liability_payable'):
                vals['reconcile'] = True
            if not acc:
                acc = Account.create({'code': code, **vals})
            else:
                has_lines = existing_move_lines.search_count([('account_id', '=', acc.id)])
                safe_vals = {'company_ids': [Command.set(companies.ids)]}
                # En base nueva podemos normalizar nombre/tipo; si ya hay movimientos,
                # no cambiamos el tipo contable de una cuenta utilizada.
                if not has_lines:
                    safe_vals.update({'name': name, 'account_type': account_type})
                    if account_type in ('asset_receivable', 'liability_payable'):
                        safe_vals['reconcile'] = True
                acc.write(safe_vals)
            accounts[code] = acc

        # Segunda pasada: jerarquia.
        for code, _name, _account_type, parent_code in ACCOUNT_SPECS:
            if parent_code and accounts[code].parent_id != accounts[parent_code]:
                if not existing_move_lines.search_count([('account_id', '=', accounts[code].id)]):
                    accounts[code].write({'parent_id': accounts[parent_code].id})

        # Odoo 20 usa account_stock_variation_id en la cuenta de valoracion.
        for valuation_code, cost_code in (
            ('1130101', '5110101'),
            ('1130102', '5110103'),
            ('1130103', '5110104'),
            ('1130104', '5110105'),
            ('1130105', '5110102'),
        ):
            if 'account_stock_variation_id' in accounts[valuation_code]._fields:
                accounts[valuation_code].write({'account_stock_variation_id': accounts[cost_code].id})
        return accounts

    def _ensure_journal(self, company, name, code, journal_type):
        Journal = self.env['account.journal'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
        journal = Journal.search([('company_id', '=', company.id), ('name', '=', name)], limit=1)
        if not journal:
            journal = Journal.create({
                'name': name,
                'code': code,
                'type': journal_type,
                'company_id': company.id,
            })
        return journal

    def _ensure_journals(self, companies):
        result = {}
        for company in companies:
            result[company.id] = {
                'sale': self._ensure_journal(company, 'Ventas - %s' % company.name, 'VTA', 'sale'),
                'purchase': self._ensure_journal(company, 'Compras - %s' % company.name, 'CMP', 'purchase'),
                'general': self._ensure_journal(company, 'Operaciones - %s' % company.name, 'OPE', 'general'),
                'stock': self._ensure_journal(company, 'Valoracion de inventario - %s' % company.name, 'STK', 'general'),
            }
        return result

    def _ensure_warehouses(self, branches):
        Warehouse = self.env['stock.warehouse'].sudo()
        result = {}
        specs = {
            'central': ('Almacen Central', 'CEN'),
            'scz': ('Almacen SCZ', 'SCZ'),
            'cbba': ('Almacen CBBA', 'CBA'),
        }
        for key, branch in branches.items():
            name, code = specs[key]
            wh = Warehouse.with_company(branch).with_context(allowed_company_ids=[branch.id]).search([
                ('company_id', '=', branch.id), ('code', '=', code)
            ], limit=1)
            if not wh:
                wh = Warehouse.with_company(branch).with_context(allowed_company_ids=[branch.id]).create({
                    'name': name, 'code': code, 'company_id': branch.id,
                })
            result[key] = wh
        return result

    def _ensure_categories(self, accounts, companies, journals):
        Category = self.env['product.category'].sudo()
        root_cat = Category.search([('name', '=', 'ESI DEMO | Soya'), ('parent_id', '=', False)], limit=1)
        if not root_cat:
            root_cat = Category.create({'name': 'ESI DEMO | Soya', 'company_id': False})
        categories = {}
        for key, name, valuation_code, income_code, expense_code in CATEGORY_SPECS:
            cat = Category.search([('name', '=', name), ('parent_id', '=', root_cat.id)], limit=1)
            if not cat:
                cat = Category.create({'name': name, 'parent_id': root_cat.id, 'company_id': False})
            categories[key] = cat
            for company in companies:
                values = {}
                fields_available = cat._fields
                if 'property_cost_method' in fields_available:
                    values['property_cost_method'] = 'average'
                elif 'cost_method' in fields_available:
                    values['cost_method'] = 'average'
                if 'property_valuation' in fields_available:
                    values['property_valuation'] = 'real_time'
                if 'property_stock_valuation_account_id' in fields_available:
                    values['property_stock_valuation_account_id'] = accounts[valuation_code].id
                if 'property_account_income_categ_id' in fields_available:
                    values['property_account_income_categ_id'] = accounts[income_code].id
                if 'property_account_expense_categ_id' in fields_available:
                    values['property_account_expense_categ_id'] = accounts[expense_code].id
                if 'property_stock_journal' in fields_available:
                    values['property_stock_journal'] = journals[company.id]['stock'].id
                if values:
                    cat.with_company(company).with_context(allowed_company_ids=[company.id]).write(values)
        return categories

    def _uom(self, key):
        refs = {
            'unit': 'uom.product_uom_unit',
            'kg': 'uom.product_uom_kgm',
            'l': 'uom.product_uom_litre',
        }
        uom = self.env.ref(refs[key], raise_if_not_found=False)
        if uom:
            return uom
        fallback = {'unit': 'Units', 'kg': 'kg', 'l': 'L'}[key]
        return self.env['uom.uom'].sudo().search([('name', '=ilike', fallback)], limit=1)

    def _ensure_products(self, categories, companies):
        Product = self.env['product.product'].sudo()
        products = {}
        for code, name, category_key, uom_key, cost, price, sale_ok, purchase_ok in PRODUCT_SPECS:
            product = Product.with_context(active_test=False).search([('default_code', '=', code)], limit=1)
            uom = self._uom(uom_key)
            if not uom:
                raise UserError(_('No se encontro la unidad requerida para %s.') % name)
            vals = {
                'name': name,
                'default_code': code,
                'categ_id': categories[category_key].id,
                'type': 'consu',
                'is_storable': True,
                'uom_id': uom.id,
                'sale_ok': sale_ok,
                'purchase_ok': purchase_ok,
                'list_price': price,
                'company_id': False,
                'description_sale': 'DEMO CORPORACION ESI - catalogo compartido entre sucursales.',
            }
            if not product:
                product = Product.create(vals)
            else:
                product.active = True
                product.write(vals)
            # El costo es company-dependent. Inicializamos el mismo costo de referencia
            # en matriz y sucursales; AVCO lo recalculara con compras/entradas posteriores.
            for company in companies:
                product.with_company(company).with_context(allowed_company_ids=[company.id]).write({'standard_price': cost})
            products[code] = product
        return products

    def _ensure_sale_purchase_types(self, branches, warehouses, journals):
        SaleType = self.env['esi.sale.type'].sudo()
        PurchaseType = self.env['esi.purchase.type'].sudo()
        result = {}
        for key, company in branches.items():
            wh = warehouses[key]
            sale_journal = journals[company.id]['sale']
            purchase_journal = journals[company.id]['purchase']
            result[company.id] = {'sale': {}, 'purchase': {}}
            for seq, name, code in (
                (10, 'VENTAS INMEDIATA', 'V-INM'),
                (20, 'VENTAS POR ENTREGAR', 'V-ENT'),
            ):
                rec = SaleType.with_company(company).with_context(allowed_company_ids=[company.id]).search([
                    ('name', '=', name), ('company_id', '=', company.id)
                ], limit=1)
                vals = {
                    'name': name, 'code': code, 'sequence': seq, 'company_id': company.id,
                    'warehouse_id': wh.id, 'journal_id': sale_journal.id,
                    'validation_picking': False, 'create_invoice': False,
                    'validate_invoice': False, 'allow_payment': True,
                    'note': 'DEMO ESI - clasificacion comercial por sucursal; la logistica sigue siendo nativa de Odoo.',
                }
                if rec:
                    rec.write(vals)
                else:
                    rec = SaleType.with_company(company).create(vals)
                result[company.id]['sale'][code] = rec
            for seq, name, code in (
                (10, 'COMPRAS INMEDIATA', 'C-INM'),
                (20, 'COMPRAS EXTERIOR', 'C-EXT'),
            ):
                rec = PurchaseType.with_company(company).with_context(allowed_company_ids=[company.id]).search([
                    ('name', '=', name), ('company_id', '=', company.id)
                ], limit=1)
                vals = {
                    'name': name, 'code': code, 'sequence': seq, 'company_id': company.id,
                    'warehouse_id': wh.id, 'journal_id': purchase_journal.id,
                    'validation_picking': False, 'create_invoice': False,
                    'validate_invoice': False, 'allow_payment': True,
                    'note': 'DEMO ESI - clasificacion de compras por sucursal; la recepcion sigue siendo nativa de Odoo.',
                }
                if rec:
                    rec.write(vals)
                else:
                    rec = PurchaseType.with_company(company).create(vals)
                result[company.id]['purchase'][code] = rec
        return result

    def _ensure_partner(self, name, supplier=False, customer=False):
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('name', '=', name)], limit=1)
        if not partner:
            vals = {'name': name, 'comment': 'DEMO CORPORACION ESI - registro ficticio'}
            if 'supplier_rank' in Partner._fields and supplier:
                vals['supplier_rank'] = 1
            if 'customer_rank' in Partner._fields and customer:
                vals['customer_rank'] = 1
            partner = Partner.create(vals)
        return partner

    def _ensure_source_balances(self, central, accounts, journals):
        Move = self.env['account.move'].sudo().with_company(central).with_context(allowed_company_ids=[central.id])
        ref = 'ESI-DEMO-SALDOS-FUENTE-AGROBALSEM'
        existing = Move.search([('company_id', '=', central.id), ('ref', '=', ref)], limit=1)
        if existing:
            return existing

        customer = self._ensure_partner('DEMO | Clientes por cobrar fuente', customer=True)
        supplier = self._ensure_partner('DEMO | Proveedores por pagar fuente', supplier=True)
        lines = []
        for code, amount, side in SOURCE_BALANCE_LINES + SOURCE_PROFIT_LINES:
            vals = {
                'name': 'Saldo fuente - %s' % accounts[code].name,
                'account_id': accounts[code].id,
                'debit': amount if side == 'd' else 0.0,
                'credit': amount if side == 'c' else 0.0,
            }
            if code == '1120101':
                vals['partner_id'] = customer.id
            elif code == '2110101':
                vals['partner_id'] = supplier.id
            lines.append(Command.create(vals))

        # Conservamos la diferencia de Bs 500 que existe en el Balance General fuente,
        # en lugar de cambiar silenciosamente alguno de sus saldos.
        lines.append(Command.create({
            'name': 'Diferencia documental Balance General fuente',
            'account_id': accounts['399998'].id,
            'debit': SOURCE_BALANCE_DOCUMENT_DIFFERENCE,
            'credit': 0.0,
        }))
        # El Estado de Resultado tiene utilidad Bs 620.700. Esta contrapartida permite
        # cargar sus saldos nominales sin alterar ninguna cifra de ingresos/costos/gastos.
        lines.append(Command.create({
            'name': 'Contrapartida tecnica Estado de Resultado fuente',
            'account_id': accounts['399999'].id,
            'debit': SOURCE_PROFIT_RESULT,
            'credit': 0.0,
        }))

        move = Move.create({
            'company_id': central.id,
            'move_type': 'entry',
            'journal_id': journals[central.id]['general'].id,
            'date': self.balance_date,
            'ref': ref,
            'line_ids': lines,
        })
        if not central.currency_id.is_zero(sum(move.line_ids.mapped('balance'))):
            raise UserError(_('El asiento de saldos fuente no cuadra. No se publico ningun movimiento.'))
        move.action_post()
        return move

    def _ensure_pricelist(self, company):
        Pricelist = self.env['product.pricelist'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
        domain = [('currency_id', '=', company.currency_id.id)]
        if 'company_id' in Pricelist._fields:
            domain += ['|', ('company_id', '=', False), ('company_id', '=', company.id)]
        pricelist = Pricelist.search(domain, limit=1)
        if not pricelist:
            vals = {'name': 'Tarifa DEMO ESI - %s' % company.name, 'currency_id': company.currency_id.id}
            if 'company_id' in Pricelist._fields:
                vals['company_id'] = company.id
            pricelist = Pricelist.create(vals)
        return pricelist

    def _ensure_draft_flow(self, branches, warehouses, types, products):
        supplier = self._ensure_partner('DEMO | Agroinsumos Bolivia SRL', supplier=True)
        customer = self._ensure_partner('DEMO | Acopiadora Oriental SA', customer=True)
        Purchase = self.env['purchase.order'].sudo()
        Sale = self.env['sale.order'].sudo()
        seed = products['SOY-SEM-001']
        fertilizer = products['SOY-FER-001']
        grain = products['SOY-GRA-001']
        for key, company in branches.items():
            wh = warehouses[key]
            p_ref = 'ESI-DEMO-RFQ-%s' % wh.code
            env_po = Purchase.with_company(company).with_context(allowed_company_ids=[company.id])
            if not env_po.search([('company_id', '=', company.id), ('partner_ref', '=', p_ref)], limit=1):
                vals = {
                    'partner_id': supplier.id,
                    'company_id': company.id,
                    'partner_ref': p_ref,
                    'esi_purchase_type_id': types[company.id]['purchase']['C-INM'].id,
                    'order_line': [
                        Command.create({'product_id': seed.id, 'name': seed.display_name, 'product_qty': 500.0, 'price_unit': 12.0, 'uom_id': seed.uom_id.id}),
                        Command.create({'product_id': fertilizer.id, 'name': fertilizer.display_name, 'product_qty': 1000.0, 'price_unit': 8.4, 'uom_id': fertilizer.uom_id.id}),
                    ],
                }
                if 'picking_type_id' in Purchase._fields and wh.in_type_id:
                    vals['picking_type_id'] = wh.in_type_id.id
                env_po.create(vals)

            s_ref = 'ESI-DEMO-SO-%s' % wh.code
            env_so = Sale.with_company(company).with_context(allowed_company_ids=[company.id])
            if not env_so.search([('company_id', '=', company.id), ('client_order_ref', '=', s_ref)], limit=1):
                vals = {
                    'partner_id': customer.id,
                    'company_id': company.id,
                    'client_order_ref': s_ref,
                    'warehouse_id': wh.id,
                    'pricelist_id': self._ensure_pricelist(company).id,
                    'esi_sale_type_id': types[company.id]['sale']['V-ENT'].id,
                    'order_line': [Command.create({
                        'product_id': grain.id,
                        'name': grain.display_name,
                        'product_uom_qty': 1000.0,
                        'price_unit': 3.2,
                    })],
                }
                env_so.create(vals)

    # ------------------------------------------------------------------
    # Main action
    # ------------------------------------------------------------------
    def action_load_demo(self):
        self.ensure_one()
        if not self.confirmation:
            raise UserError(_('Marque la confirmacion de base nueva / demostracion antes de continuar.'))

        root, branches, companies = self._ensure_companies()
        accounts = self._ensure_accounts(root, companies)
        journals = self._ensure_journals(companies)
        warehouses = self._ensure_warehouses(branches)
        categories = self._ensure_categories(accounts, companies, journals)
        products = self._ensure_products(categories, companies)
        types = self._ensure_sale_purchase_types(branches, warehouses, journals)
        move = self._ensure_source_balances(branches['central'], accounts, journals)
        if self.create_draft_flow:
            self._ensure_draft_flow(branches, warehouses, types, products)

        summary = _(
            'DEMO preparada correctamente.\n'
            '- Matriz: CORPORACION ESI.\n'
            '- Sucursales: CENTRAL, SCZ y CBBA.\n'
            '- 3 almacenes, uno por sucursal.\n'
            '- Plan contable compartido entre matriz y sucursales.\n'
            '- 20 productos compartidos: 15 insumos, 3 cosechados y 2 de apoyo.\n'
            '- Categorias: AVCO + valoracion automatica/perpetua.\n'
            '- Tipos por sucursal: VENTAS INMEDIATA, VENTAS POR ENTREGAR, COMPRAS INMEDIATA y COMPRAS EXTERIOR.\n'
            '- Saldos fuente publicados en SUCURSAL CENTRAL con ref. %s.\n'
            '- Diferencia documental del Balance fuente: Bs 500, conservada en cuenta 399998.\n'
            '- Resultado del Estado de Resultado fuente: Bs 620.700; contrapartida tecnica en 399999.\n'
            '%s'
        ) % (move.ref, '- Se crearon RFQ/cotizaciones en borrador por sucursal.\n' if self.create_draft_flow else '')
        self.result_summary = summary
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
