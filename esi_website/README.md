# ESI Website — Odoo 20.0 Community

Módulo técnico: `esi_website`. Destino de producción solicitado: **ESIBOLIVIA**.
Dominio previsto: **https://www.esibolivia-odoo.online**.

## Estado y alcance

Preparado para Odoo 20.0 Community. **No se verificó la instalación en un servidor
Odoo 20 real. Es obligatorio probarlo primero en una copia aislada de la base.**
Durante la preparación no se conectó ni modificó ninguna base de datos.

Se conserva el HTML publicado del sitio B12 y sus estilos compilados, con las
11 secciones originales, iconos SVG y fotografía de portada locales. Los originales
`index.astro` y `global.css` se incluyen en `originales/` como referencia. La cabecera
y el pie proceden del HTML publicado, no de una reconstrucción inventada.
El logotipo oficial reemplaza la marca tipográfica provisional. Se elimina el
sello de B12 y sus scripts de analítica, editor, reCAPTCHA y envío de formularios.
La tipografía conserva la pila original Inter / system-ui; el original consultado
no suministra un archivo Inter. Se usará la fuente de sistema si Inter no está instalada.
No se incorpora un favicon nuevo.

La página se sirve mediante un documento QWeb independiente y un paquete de
recursos `esi_website.assets` para evitar que Bootstrap u otros temas alteren el
diseño original. No usa el editor visual de bloques de Odoo; los cambios de diseño
se realizan en las plantillas y estilos del módulo. El menú móvil usa JavaScript local.

## Formulario

Dependencias: `website` y `crm` (Community). Cada envío válido crea una oportunidad
CRM sin vendedor ni equipo asignados, en la compañía del sitio web actual.
Campos: nombre, empresa, teléfono, correo, rubro y mensaje. Usa validación en
servidor, token CSRF, campos permitidos explícitos, escape HTML y campo antirrobots.
Hay un intervalo mínimo de 60 segundos por sesión entre envíos correctos; no es
una protección global contra ataques. No necesita B12, claves API ni SMTP.
No promete ni envía correos automáticamente: revisar las solicitudes en CRM.
Si CRM tiene filtros de «Mis oportunidades», quitarlos para ver las no asignadas.

## 1. Prueba en una copia aislada

1. Descomprime el ZIP. Copia la carpeta `esi_website` completa a una ruta de addons
   del entorno de pruebas. Debe contener directamente `__manifest__.py`.
2. Utiliza una copia aislada de ESIBOLIVIA con Odoo **20.0 Community**, sin correos
   salientes ni conexiones externas de producción. No pruebes sobre la base real.
3. Reinicia únicamente Odoo de pruebas para cargar los controladores Python.
4. Activa modo desarrollador, actualiza la lista de aplicaciones y busca
   «ESI Website». Instálalo únicamente dentro de la copia de pruebas.
5. Abre `/esi` y `/`. Comprueba escritorio (1440 px), tableta (768 px) y móvil
   (390 px): logo, fotografía, menú, anclas, columnas, SVG, WhatsApp y correo.
6. Envía una solicitud ficticia. Verifica confirmación y una sola oportunidad CRM
   con todos los campos. Prueba correo inválido, campos vacíos, CSRF ausente,
   doble envío, recarga y botón atrás. Comprueba que el texto HTML introducido
   en el mensaje se muestra como texto, no como código ejecutable.
7. Revisa los logs: sin errores QWeb, assets, permisos ni campos inexistentes.
8. Comprueba acceso al backend mediante `/web/login` y el flujo normal de trabajo.

## 2. Instalación en ESIBOLIVIA tras aprobar la prueba

Realiza previamente una copia de seguridad de base y filestore. Usa la misma
carpeta probada. Colócala en el directorio de addons que ya utiliza tu instancia.
Por ejemplo, si esa ruta está en tu configuración:
`/opt/odoo20/odoo01/addons/EsiOdoo20/esi_website`.

Reinicia la instancia correspondiente, entra expresamente en **ESIBOLIVIA**,
actualiza la lista de aplicaciones e instala «ESI Website». No uses «-d all», no
actualices módulos de otras bases ni instales este módulo en ellas. La existencia
de la carpeta compartida no instala el módulo en otras bases. Este módulo no
incluye scripts SQL, cambios de configuración ni conexiones a otras bases.

El nombre de base no está fijado en el código: así se puede probar en una copia.
La selección de **ESIBOLIVIA** es responsabilidad del proceso de instalación.
No sustituir ese nombre por ESIBOLIVIA0001 sin comprobar el nombre real autorizado.

## 3. Dominio y página de inicio

Al instalar, las rutas `/`, `/index` y `/esi` muestran el sitio ESI **en la base donde
se instala**. Esto afecta a todos los sitios web de esa base; para un entorno
multisitio hace falta adaptar el alcance antes de instalar. No elimina páginas
anteriores ni modifica registros de contenido ajenos al módulo.

Configura en el sitio web de esa base el dominio `https://www.esibolivia-odoo.online`.
DNS, certificado TLS para `www`, proxy y selección de base deben apuntar a esa
instancia. El módulo no configura Nginx, Docker, DNS, SSL ni dbfilter. No fija
web.base.url ni redirige otras bases. Conserva tus rutas de acceso al backend.

## Actualización y retirada

Para actualizar: reemplaza la carpeta, reinicia la instancia y actualiza solo
`esi_website` dentro de la base elegida. Para retirar: desinstálalo desde Aplicaciones
y reinicia la instancia. Se retiran las vistas/recursos del módulo; las oportunidades
CRM ya creadas permanecen. Verifica la página de inicio anterior tras retirarlo.

## Archivos principales

- `views/templates.xml`: página QWeb con el contenido original.
- `controllers/main.py`: portada y recepción de asesorías.
- `static/src/css/website.css`: CSS original compilado y ajustes del logotipo.
- `static/src/js/website.js`: menú móvil y estado de envío.
- `static/src/img/`: fotografía y logotipo, sin dependencias de CDN.
- `originales/`: Astro y CSS recibidos, conservados para mantenimiento.
- `VALIDACION.md`: verificaciones locales y límites.

Referencia original: https://esi-especialistas-en-sistemas-integrados-staging.b12sites.com/
Referencia técnica: https://www.odoo.com/documentation/20.0/developer/reference/backend/http.html
