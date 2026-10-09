from odoo import models

class Document0(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'esi.branch.mixin']

class Document1(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'esi.branch.mixin']

class Document2(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'esi.branch.mixin']

class Document3(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'esi.branch.mixin']

class Document4(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'esi.branch.mixin']

class Document5(models.Model):
    _name = 'account.move.line'
    _inherit = ['account.move.line', 'esi.branch.mixin']

class Document6(models.Model):
    _name = 'account.journal'
    _inherit = ['account.journal', 'esi.branch.mixin']

class Document7(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'esi.branch.mixin']

class Document8(models.Model):
    _name = 'stock.warehouse'
    _inherit = ['stock.warehouse', 'esi.branch.mixin']

class Document9(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'esi.branch.mixin']

class Document10(models.Model):
    _name = 'stock.picking.type'
    _inherit = ['stock.picking.type', 'esi.branch.mixin']

class Document11(models.Model):
    _name = 'stock.warehouse.orderpoint'
    _inherit = ['stock.warehouse.orderpoint', 'esi.branch.mixin']

class Document12(models.Model):
    _name = 'stock.move'
    _inherit = ['stock.move', 'esi.branch.mixin']

class Document13(models.Model):
    _name = 'stock.move.line'
    _inherit = ['stock.move.line', 'esi.branch.mixin']

class Document14(models.Model):
    _name = 'stock.quant'
    _inherit = ['stock.quant', 'esi.branch.mixin']

class Document15(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'esi.branch.mixin']

