from odoo import api, models


class FinanceSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _esi_retire_classic_extension_views(self):
        # Keep previously configured orders; do not uninstall or delete their model/data.
        for name in ('classic_wizard_form', 'order_menu'):
            record = self.env.ref('esi_financieros_clasicos_v20.'+name, raise_if_not_found=False)
            if record and 'active' in record._fields:
                record.write({'active': False})
        return True
