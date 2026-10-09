from odoo import models

class Branch0(models.TransientModel):
    _name = 'esi.production.report'
    _inherit = ['esi.production.report', "esi.branch.mixin"]

