import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EsiDataCleanupWizard(models.TransientModel):
    _name = "esi.data.cleanup.wizard"
    _description = "Limpieza de datos por sucursal"

    scope = fields.Selection(
        [("selected", "Sucursales seleccionadas"), ("all", "Todas las sucursales permitidas")],
        string="Alcance",
        required=True,
        default="selected",
    )
    allowed_company_ids = fields.Many2many(
        "res.company",
        compute="_compute_allowed_companies",
        string="Sucursales permitidas",
    )
    company_ids = fields.Many2many(
        "res.company",
        "esi_cleanup_wizard_company_rel",
        "wizard_id",
        "company_id",
        string="Sucursales / Compañías",
        default=lambda self: self.env.company,
    )
    confirmation = fields.Char(
        string="Confirmación",
        help="Escriba LIMPIAR para habilitar las acciones destructivas.",
    )
    can_clean = fields.Boolean(compute="_compute_can_clean")
    target_summary = fields.Char(compute="_compute_target_summary", string="Alcance efectivo")

    @api.depends_context("allowed_company_ids")
    def _compute_allowed_companies(self):
        for wizard in self:
            wizard.allowed_company_ids = self.env.companies

    @api.depends("confirmation")
    def _compute_can_clean(self):
        for wizard in self:
            wizard.can_clean = (wizard.confirmation or "").strip().upper() == "LIMPIAR"

    @api.depends("scope", "company_ids", "allowed_company_ids")
    def _compute_target_summary(self):
        for wizard in self:
            companies = wizard._target_companies(check=False)
            wizard.target_summary = ", ".join(companies.mapped("name")) if companies else _("Ninguna sucursal seleccionada")

    def _target_companies(self, check=True):
        self.ensure_one()
        allowed = self.env.companies
        companies = allowed if self.scope == "all" else self.company_ids & allowed
        if check and not companies:
            raise UserError(_("Seleccione al menos una sucursal / compañía activa en su sesión."))
        return companies

    def _ensure_authorized(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Solo un administrador de Ajustes puede ejecutar la limpieza de datos."))
        if not self.can_clean:
            raise UserError(_("Escriba LIMPIAR en el campo de confirmación antes de continuar."))
        return self._target_companies()

    def _model_exists(self, model_name):
        return model_name in self.env

    def _delete_company_records(self, model_name, company_ids, extra_domain=None):
        """Delete only records whose model exposes a real company_id field.

        We intentionally do not fall back to unscoped SQL. Models without a
        company_id are skipped; this prevents shared/global master data from
        being destroyed while cleaning one branch.
        """
        if not self._model_exists(model_name):
            return 0
        Model = self.env[model_name].sudo().with_context(active_test=False, allowed_company_ids=company_ids)
        if "company_id" not in Model._fields:
            # Known accounting bridge model: its company is determined by the
            # debit/credit move lines. Delete only reconciliations touching the
            # selected companies so account.move.line can then be removed.
            if model_name == "account.partial.reconcile":
                records = Model.search([
                    "|",
                    ("debit_move_id.company_id", "in", company_ids),
                    ("credit_move_id.company_id", "in", company_ids),
                ])
                count = len(records)
                if count:
                    records.unlink()
                return count
            _logger.info("ESI cleanup: skipped %s (no company_id)", model_name)
            return 0
        domain = [("company_id", "in", company_ids)]
        if extra_domain:
            domain += extra_domain
        records = Model.search(domain)
        count = len(records)
        if not count:
            return 0
        # Destructive maintenance tool: direct table delete avoids business
        # workflow guards, but remains strictly company-filtered.
        table = Model._table
        query = f'DELETE FROM "{table}" WHERE company_id = ANY(%s)'
        self.env.cr.execute(query, [company_ids])
        return count

    def _clean_models(self, models_to_clean):
        companies = self._ensure_authorized()
        ids = companies.ids
        total = 0
        # Child/detail tables first when they have company_id, then parents.
        for model_name in models_to_clean:
            try:
                with self.env.cr.savepoint():
                    total += self._delete_company_records(model_name, ids)
            except Exception as exc:
                _logger.warning("ESI cleanup could not clean %s: %s", model_name, exc)
        self.env.invalidate_all()
        return self._done(companies, total)

    def _done(self, companies, total):
        names = ", ".join(companies.mapped("name"))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Limpieza finalizada"),
                "message": _("Se procesaron %(count)s registros para: %(companies)s", count=total, companies=names),
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_clean_sales(self):
        return self._clean_models(["sale.order.line", "sale.order"])

    def action_clean_purchase(self):
        return self._clean_models(["purchase.order.line", "purchase.order"])

    def action_clean_pos(self):
        return self._clean_models(["pos.payment", "pos.order.line", "pos.order", "pos.session"])

    def action_clean_mrp(self):
        return self._clean_models([
            "mrp.workcenter.productivity", "mrp.workorder", "mrp.production", "mrp.unbuild"
        ])

    def action_clean_inventory(self):
        return self._clean_models([
            "stock.move.line", "stock.move", "stock.picking", "stock.scrap",
            "stock.quant", "stock.valuation.layer", "stock.lot"
        ])

    def action_clean_account(self):
        return self._clean_models([
            "account.partial.reconcile", "account.payment", "account.move.line", "account.move",
            "account.bank.statement.line"
        ])

    def action_clean_expense(self):
        return self._clean_models(["hr.expense", "hr.expense.sheet"])

    def action_clean_project(self):
        return self._clean_models(["project.task", "project.project"])

    def action_clean_quality(self):
        return self._clean_models(["quality.check", "quality.alert"])

    def action_clean_all_operations(self):
        return self._clean_models([
            "pos.payment", "pos.order.line", "pos.order", "pos.session",
            "sale.order.line", "sale.order",
            "purchase.order.line", "purchase.order",
            "mrp.workcenter.productivity", "mrp.workorder", "mrp.production", "mrp.unbuild",
            "stock.move.line", "stock.move", "stock.picking", "stock.scrap", "stock.quant", "stock.valuation.layer", "stock.lot",
            "account.partial.reconcile", "account.payment", "account.move.line", "account.move", "account.bank.statement.line",
            "hr.expense", "hr.expense.sheet", "project.task", "project.project", "quality.check", "quality.alert",
        ])
