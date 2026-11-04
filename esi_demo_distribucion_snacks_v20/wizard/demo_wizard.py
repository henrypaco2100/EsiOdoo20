from odoo import fields, models, _
from odoo.exceptions import UserError


class EsiSnackWizard(models.TransientModel):
    _name = "esi.snack.wizard"
    _description = "Carga opcional de ejemplos de distribución de snacks"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    confirm_test = fields.Boolean(string="Confirmo que esta es una base de pruebas")

    def action_load(self):
        self.ensure_one()
        if not self.confirm_test:
            raise UserError(_("Confirma primero que estás trabajando en una base de pruebas."))
        company = self.company_id
        Product = self.env["product.template"].sudo().with_company(company)
        Partner = self.env["res.partner"].sudo().with_company(company)
        Category = self.env["product.category"].sudo().with_company(company)
        category = Category.search([("name", "=", "ESI Snacks - Distribución")], limit=1)
        if not category:
            cat_values = {"name": "ESI Snacks - Distribución"}
            if "property_cost_method" in Category._fields:
                cat_values["property_cost_method"] = "average"
            category = Category.create(cat_values)
        elif "property_cost_method" in Category._fields and category.property_cost_method != "average":
            raise UserError(_("La categoría de ejemplo existente no utiliza AVCO. Revísala antes de continuar."))
        products = [
            ("SNACK-ESI-001", "Papas fritas clásicas 45 g", 4.5, 2.8),
            ("SNACK-ESI-002", "Papas fritas picantes 45 g", 4.5, 2.8),
            ("SNACK-ESI-003", "Chizitos 35 g", 3.5, 2.1),
            ("SNACK-ESI-004", "Palitos salados 40 g", 3.5, 2.0),
            ("SNACK-ESI-005", "Maní salado 50 g", 5.0, 3.2),
            ("SNACK-ESI-006", "Galletas saladas paquete", 6.0, 3.8),
            ("SNACK-ESI-007", "Chocolatina pequeña", 4.0, 2.6),
            ("SNACK-ESI-008", "Gomitas bolsa 50 g", 5.0, 3.0),
        ]
        for code, name, price, cost in products:
            product = Product.search([("default_code", "=", code)], limit=1)
            if not product:
                vals = {
                    "name": name,
                    "default_code": code,
                    "list_price": price,
                    "standard_price": cost,
                    "categ_id": category.id,
                    "sale_ok": True,
                    "purchase_ok": True,
                }
                if "company_id" in Product._fields:
                    vals["company_id"] = company.id
                if "is_storable" in Product._fields:
                    vals["is_storable"] = True
                Product.create(vals)
        customers = [
            ("SNACK-CLIENTE-001", "Tienda El Buen Vecino"),
            ("SNACK-CLIENTE-002", "Kiosco Central"),
            ("SNACK-CLIENTE-003", "Minimercado Los Amigos"),
            ("SNACK-CLIENTE-004", "Tienda La Esquina"),
        ]
        Visit = self.env["esi.snack.visit"].with_company(company)
        for i, (ref, name) in enumerate(customers):
            partner = Partner.search([("ref", "=", ref)], limit=1)
            if not partner:
                vals = {"name": name, "ref": ref}
                if "company_id" in Partner._fields:
                    vals["company_id"] = company.id
                partner = Partner.create(vals)
            if not Visit.search([("partner_id", "=", partner.id), ("company_id", "=", company.id), ("notes", "=", "Visita de presentación")], limit=1):
                Visit.create({
                    "partner_id": partner.id,
                    "company_id": company.id,
                    "scheduled_date": fields.Date.context_today(self),
                    "notes": "Visita de presentación",
                    "state": "planned",
                })
        return {
            "type": "ir.actions.act_window",
            "name": _("Visitas de distribución"),
            "res_model": "esi.snack.visit",
            "view_mode": "list,form",
            "domain": [("company_id", "=", company.id)],
        }
