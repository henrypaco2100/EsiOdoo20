from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EsiSnackVisit(models.Model):
    _name = "esi.snack.visit"
    _description = "Visita a cliente - distribucion de snacks"
    _order = "scheduled_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Referencia", required=True, default=lambda self: _("Nueva visita"), copy=False)
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company, required=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Cliente / tienda", required=True, index=True,
                                 domain="[('customer_rank', '>=', 0)]")
    user_id = fields.Many2one("res.users", string="Distribuidor", default=lambda self: self.env.user, required=True)
    scheduled_date = fields.Date(string="Fecha programada", required=True, default=fields.Date.context_today, index=True)
    visited_date = fields.Date(string="Fecha visitada")
    next_visit_date = fields.Date(string="Próxima visita")
    state = fields.Selection([
        ("planned", "Pendiente"),
        ("visited", "Visitado"),
        ("no_contact", "No se encontró al cliente"),
        ("cancelled", "Cancelada"),
    ], string="Estado", default="planned", required=True, index=True)
    notes = fields.Text(string="Observaciones / productos solicitados")
    order_id = fields.Many2one("sale.order", string="Pedido / cotización", readonly=True, copy=False)
    order_amount = fields.Monetary(string="Importe del pedido", related="order_id.amount_total", readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("Nueva visita"):
                vals["name"] = self.env["ir.sequence"].next_by_code("esi.snack.visit") or _("Nueva visita")
        return super().create(vals_list)

    def action_mark_visited(self):
        for visit in self:
            visit.write({"state": "visited", "visited_date": fields.Date.context_today(visit)})
        return True

    def action_mark_no_contact(self):
        self.write({"state": "no_contact", "visited_date": fields.Date.context_today(self)})
        return True

    def action_reset_planned(self):
        self.write({"state": "planned"})
        return True

    def action_create_quotation(self):
        self.ensure_one()
        if self.order_id:
            return self.action_open_quotation()
        order = self.env["sale.order"].with_company(self.company_id).create({
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "origin": self.name,
            "note": self.notes or "",
        })
        self.order_id = order.id
        return self.action_open_quotation()

    def action_open_quotation(self):
        self.ensure_one()
        if not self.order_id:
            raise UserError(_("Todavía no hay un pedido asociado a esta visita."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pedido del cliente"),
            "res_model": "sale.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_print_visit(self):
        self.ensure_one()
        return self.env.ref("esi_demo_distribucion_snacks_v20.action_report_snack_visit").report_action(self)
