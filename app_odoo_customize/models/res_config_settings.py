from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    esi_system_name = fields.Char(
        string="Nombre del sistema",
        config_parameter="app_odoo_customize.esi_system_name",
        default="ESI ERP",
    )

    def action_open_esi_cleanup(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Limpieza de datos por sucursal",
            "res_model": "esi.data.cleanup.wizard",
            "view_mode": "form",
            "target": "new",
        }
