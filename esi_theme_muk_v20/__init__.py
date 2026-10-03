from odoo.tools import BinaryBytes, file_open


def post_init_hook(env):
    # Seed ESI colors through MuK's own editor, preserving existing custom palettes.
    editor = env['muk_web_colors.color_assets_editor']
    palettes = [
        ('/muk_web_colors/static/src/colors/light/light.scss', 'web._assets_primary_variables',
         {'color_brand': '#072955', 'color_primary': '#009846', 'color_success': '#009846'}),
        ('/muk_web_theme/static/src/colors/theme/theme.scss', 'web._assets_primary_variables',
         {'color_appsmenu_text': '#FFFFFF', 'color_appbar_text': '#FFFFFF',
          'color_appbar_active': '#009846', 'color_appbar_background': '#072955'}),
    ]
    for url, bundle, values in palettes:
        custom_url = editor._get_custom_colors_url(url, bundle)
        if not editor._get_colors_attachment(custom_url):
            editor.write_colors(url, bundle, values)
    company = env.ref('base.main_company', raise_if_not_found=False)
    if company:
        with file_open('web/static/img/favicon.ico', 'rb') as f:
            original = f.read()
        if not company.favicon or company.favicon.content == original:
            with file_open('esi_theme_core_v20/static/src/img/favicon.png', 'rb') as f:
                company.favicon = BinaryBytes(f.read(), filename='favicon.png')
