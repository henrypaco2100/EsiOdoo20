from odoo import models

class Branch0(models.Model):
    _name = 'pos.config'
    _inherit = ['pos.config', "esi.branch.mixin"]

class Branch1(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', "esi.branch.mixin"]

class Branch2(models.Model):
    _name = 'pos.session'
    _inherit = ['pos.session', "esi.branch.mixin"]

