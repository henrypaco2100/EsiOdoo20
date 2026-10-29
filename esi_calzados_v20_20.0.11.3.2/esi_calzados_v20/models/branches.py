from odoo import models

class Branch0(models.Model):
    _name = 'esi.production.group'
    _inherit = ['esi.production.group', "esi.branch.mixin"]

class Branch1(models.Model):
    _name = 'esi.destajo'
    _inherit = ['esi.destajo', "esi.branch.mixin"]

