from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.pos.report'
    _inherit = ['esi.pos.report', "esi.branch.mixin"]

