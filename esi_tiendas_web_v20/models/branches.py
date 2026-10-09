from odoo import models

class Branch0(models.Model):
    _name = 'website'
    _inherit = ['website', "esi.branch.mixin"]

