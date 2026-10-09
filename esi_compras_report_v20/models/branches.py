from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.purchase.report'
    _inherit = ['esi.purchase.report', "esi.branch.mixin"]

