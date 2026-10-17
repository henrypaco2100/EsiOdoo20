import re
import time

from markupsafe import Markup, escape
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website

LIMITS = {'nombre': 254, 'empresa': 254, 'telefono': 80, 'correo': 254,
          'rubro': 80, 'mensaje': 4000}
SECTORS = {'Importadora', 'Distribuidora', 'Agropecuaria', 'Manufactura', 'Farmacia', 'Comercio'}


def validate_form(data):
    values = {key: str(data.get(key, '')).strip() for key in LIMITS}
    if any(not value for value in values.values()):
        return values, 'Completa todos los campos obligatorios.'
    if any(len(values[key]) > limit for key, limit in LIMITS.items()):
        return values, 'Uno de los campos supera el tamaño permitido.'
    if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', values['correo']):
        return values, 'Introduce un correo electrónico válido.'
    if values['rubro'] not in SECTORS:
        return values, 'Selecciona un rubro de la lista.'
    return values, None


class ESIWebsite(Website):
    @http.route(['/', '/index'], type='http', auth='public', website=True,
                methods=['GET'], sitemap=False)
    def index(self, **kw):
        # /esi is served by Odoo's native website.page pipeline. It supplies
        # main_object, editable metadata and enforces publication/access rules.
        page = request.env.ref('esi_website.page_esi_home', raise_if_not_found=False)
        if page:
            return request.redirect(page.sudo().url, code=302)
        return super().index(**kw)

    @http.route('/esi/asesoria', type='http', auth='public', website=True,
                methods=['POST'], csrf=True, sitemap=False)
    def advice(self, **post):
        # Only explicit business fields reach the ORM; no client-controlled model,
        # company, user, team, record ID or redirect is accepted.
        page = request.env.ref('esi_website.page_esi_home', raise_if_not_found=False)
        if not page or not (page.sudo().is_visible or request.env.user.has_group('website.group_website_designer')):
            return request.not_found()
        values, error = validate_form(post)
        if post.get('website_url'):
            error = 'No se pudo procesar la solicitud. Escríbenos por WhatsApp.'
        now = time.time()
        if now - float(request.session.get('esi_last_advice', 0)) < 60:
            error = 'Espera un minuto antes de enviar otra solicitud.'
        if error:
            request.session['esi_form_values'] = {key: value[:LIMITS[key]] for key, value in values.items()}
            request.session['esi_form_error'] = error
            return request.redirect('/esi#contacto', code=303)
        description = Markup('<p><b>Rubro:</b> %s</p><p>%s</p>') % (
            escape(values['rubro']), escape(values['mensaje']).replace('\n', Markup('<br/>')))
        company = request.website.company_id
        request.env['crm.lead'].sudo().with_company(company).create({
            'name': 'Asesoría web — %s' % values['empresa'],
            'contact_name': values['nombre'],
            'partner_name': values['empresa'],
            'phone': values['telefono'],
            'email_from': values['correo'],
            'description': description,
            'type': 'opportunity',
            'company_id': company.id,
            'user_id': False,
            'team_id': False,
        })
        request.session['esi_last_advice'] = now
        request.session['esi_advice_success'] = True
        return request.redirect('/esi#contacto', code=303)
