from odoo import api, models


class WebsitePage(models.Model):
    _inherit = 'website.page'

    @api.model
    def _allow_to_use_cache(self, request):
        # The form contains a session-specific CSRF token and feedback.
        # Includes editor-created per-website copies of this template.
        info = self._get_page_info(request)
        if info:
            page = self.sudo().browse(info['id'])
            if page.view_id.key == 'esi_website.homepage':
                return False
        return super()._allow_to_use_cache(request)
