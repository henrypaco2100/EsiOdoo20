from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.finance.report'
    _inherit = ['esi.finance.report', "esi.branch.mixin"]

