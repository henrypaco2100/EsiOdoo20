from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.sales.report'
    _inherit = ['esi.sales.report', "esi.branch.mixin"]

