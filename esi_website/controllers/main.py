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
    @http.route(['/', '/index', '/esi'], type='http', auth='public', website=True,
                methods=['GET'], sitemap=True)
    def index(self, **kw):
        success = bool(request.session.pop('esi_advice_success', False))
        return request.render('esi_website.homepage', {
            'values': {}, 'error': None, 'success': success,
        }, headers={'Cache-Control': 'no-store'})

    @http.route('/esi/asesoria', type='http', auth='public', website=True,
                methods=['POST'], csrf=True, sitemap=False)
    def advice(self, **post):
        # Only explicit business fields reach the ORM; no client-controlled model,
        # company, user, team, record ID or redirect is accepted.
        values, error = validate_form(post)
        if post.get('website_url'):
            error = 'No se pudo procesar la solicitud. Escríbenos por WhatsApp.'
        now = time.time()
        if now - float(request.session.get('esi_last_advice', 0)) < 60:
            error = 'Espera un minuto antes de enviar otra solicitud.'
        if error:
            return request.render('esi_website.homepage', {
                'values': values, 'error': error, 'success': False,
            }, status=400, headers={'Cache-Control': 'no-store'})
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
        return request.redirect('/#contacto', code=303)
