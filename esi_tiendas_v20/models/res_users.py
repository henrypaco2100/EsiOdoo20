from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    esi_store_id = fields.Many2one(
        'esi.store', string='Tienda ESI actual',
        domain="[('company_id', '=', company_id)]",
        user_writeable=True,
        help='Solo sirve como valor por defecto comercial/analítico. No limita almacenes ni documentos.',
    )
    esi_store_ids = fields.Many2many(
        'esi.store', 'esi_store_user_rel', 'user_id', 'store_id', string='Tiendas ESI permitidas',
        help='Lista informativa/operativa. Este módulo no crea reglas de registro sobre stock.',
    )

    @api.constrains('esi_store_id', 'esi_store_ids')
    def _check_esi_store(self):
        for user in self:
            if user.esi_store_id and user.esi_store_ids and user.esi_store_id not in user.esi_store_ids:
                raise ValidationError(_('La tienda actual debe estar incluida en las tiendas permitidas del usuario.'))
