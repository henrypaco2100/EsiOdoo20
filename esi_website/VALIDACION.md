# Verificación 20.0.1.1.0

Comprobaciones locales ejecutadas:
- Python válido y JavaScript sin errores de sintaxis.
- XML de plantilla y registro de página válidos.
- website.layout y contenedor #wrap.oe_structure presentes.
- Once secciones conservadas.
- Manifest actualizado y recursos registrados en web.assets_frontend.
- CSS limitado al contenedor ESI; sin reset global Tailwind.
- Sin ruta GET /esi: la página utiliza el control nativo de publicación.
- Registro de página separado de la vista, con publicación inicial y noupdate.
- Caché de la página con formulario desactivada.
- ZIP íntegro y sin archivos compilados Python.

Pendiente: instalación/actualización en Odoo 20 real; visibilidad de los botones;
editar y guardar; publicar/despublicar e incógnito; envío de formulario y CRM;
comprobación visual de escritorio/móvil con los módulos instalados del usuario.

Referencias técnicas consultadas (rama master, puede diferir de tu build 20.0):
https://github.com/odoo/odoo/blob/master/addons/website/models/website_page.py
https://github.com/odoo/odoo/blob/master/addons/website/models/ir_http.py
https://github.com/odoo/odoo/blob/master/addons/website/views/website_templates.xml
