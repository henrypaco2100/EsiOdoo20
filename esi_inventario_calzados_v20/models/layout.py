"""Readable matrix layout for the screen and the A3 PDF (no ORM)."""
from html import escape


def column_width(header):
    return {'Sucursal / compañía': 120, 'Moneda': 60, 'Código': 180,
            'Descripción': 360, 'Unidad': 65, 'PU': 85, 'TOTAL': 65,
            'Valor': 115}.get(header, 44)


def render_matrix(title, headers, rows, print_mode=False):
    widths = [column_width(h) for h in headers]
    total_width = sum(widths)
    font = '8pt' if print_mode else '12px'
    table_style = 'border-collapse:collapse;table-layout:fixed;font-size:%s;' % font
    table_style += 'width:100%;' if print_mode else 'width:%spx;min-width:100%%;' % total_width
    parts = ['<div class="esi-size-report"><h3>%s</h3>' % escape(title),
             '<p>PU: costo actual por unidad. Existencias propias, sin consignación. Variable: costos distintos por talla.</p>']
    if not print_mode:
        parts.append('<p>Desplace la tabla horizontalmente para consultar todas las tallas y el valor.</p>')
    parts.append('<div class="esi-size-scroll" style="%s">' % ('' if print_mode else 'overflow-x:auto;max-width:100%;'))
    parts.append('<table class="esi-size-matrix" style="%s"><colgroup>' % table_style)
    for width in widths:
        parts.append('<col style="width:%.4f%%;"/>' % (100 * width / total_width))
    parts.append('</colgroup><thead style="display:table-header-group;"><tr>')
    for header, width in zip(headers, widths):
        parts.append('<th style="width:%.4f%%;padding:6px 4px;border:1px solid #b6c4d2;background:#072955;color:white;vertical-align:middle;word-break:normal;white-space:normal;">%s</th>' % (100*width/total_width, escape(str(header))))
    parts.append('</tr></thead><tbody>')
    description_index = headers.index('Descripción')
    for i, row in enumerate(rows):
        is_total = row[description_index] == 'TOTAL'
        bg = '#e2efda' if is_total else '#f3f6f9' if i % 2 else '#ffffff'
        parts.append('<tr style="page-break-inside:avoid;background:%s;%s">' % (bg,'font-weight:bold;' if is_total else ''))
        for header, value in zip(headers, row):
            numeric = isinstance(value, (int, float))
            if numeric:
                text = ('{:,.2f}'.format(value) if header in ('PU','Valor') else '{:,.3f}'.format(value).rstrip('0').rstrip('.'))
            else:
                text = str(value if value is not None else '')
            # Wrap descriptions and long references at readable word/hyphen boundaries.
            wrap = 'white-space:normal;overflow-wrap:break-word;word-break:normal;' if header in ('Descripción','Código','Sucursal / compañía') else 'white-space:nowrap;'
            align = 'right' if numeric else 'left'
            parts.append('<td style="padding:6px 4px;border:1px solid #d4dde5;vertical-align:top;text-align:%s;%s">%s</td>' % (align,wrap,escape(text)))
        parts.append('</tr>')
    parts.append('</tbody></table></div></div>')
    return ''.join(parts)
