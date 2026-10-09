from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.kardex.report'
    _inherit = ['esi.kardex.report', "esi.branch.mixin"]

