# ESI Website 20.0.1.1.0 — Editor y publicación

Módulo técnico: `esi_website`. Actualiza la versión 20.0.1.0.0; no es otro módulo.
Destino de producción solicitado: ESIBOLIVIA. Primero probar en una copia.

## Corrección

La primera versión entregaba HTML independiente mediante un controlador. Eso
omitía website.layout, el registro website.page y las zonas editables que necesita
Odoo. No modificaba permisos, pero impedía usar sus controles nativos.

Esta versión:
- Usa `website.layout`, el paquete `web.assets_frontend` y `#wrap.oe_structure`.
- Registra «ESI — Inicio» como página real de Odoo, inicialmente publicada.
- Sirve `/esi` mediante el mecanismo nativo de páginas de Odoo, que controla la
  visibilidad, la publicación y los metadatos del editor. No hay ruta Python GET
  que muestre el contenido saltándose el estado de publicación.
- Redirige `/` y `/index` a esa página. La dirección final es `/esi`.
- Conserva las once secciones, fotografía, logotipo y contenido B12.
- Limita el CSS a `.esi-site`, para no cambiar la barra ni los paneles de Odoo.
- Permite editar textos, imágenes y contenido de las zonas editables. El formulario
  funcional está protegido contra ediciones accidentales de sus campos técnicos.
- No cambia grupos, usuarios, permisos, otras bases, Docker, DNS ni Nginx.

El diseño sigue siendo personalizado. No todas las opciones de diseño específicas
de los bloques estándar de Odoo se aplican a cada tarjeta personalizada.

## Actualizar la instalación existente

1. Respalda la base y el filestore. Prueba estos pasos primero en una copia aislada.
2. Reemplaza la carpeta anterior `esi_website` por la carpeta de este ZIP en tu
   directorio de addons. No coloques una carpeta `esi_website` dentro de otra.
3. Reinicia el servicio/contenedor Odoo correspondiente. Es necesario descargar
   las rutas Python de la versión anterior; actualizar solo XML no basta.
4. Entra en la base elegida, abre Aplicaciones, busca «ESI Website» y pulsa
   **Actualizar** en el módulo existente. No basta con actualizar la lista de apps.
   No hace falta desinstalar la versión anterior.
5. Abre Sitio web → Ir al sitio web y entra en `/esi`. Recarga con Ctrl+F5.
6. Con tu usuario «Editor y diseñador», verifica **Editar** y el interruptor
   **Publicado / No publicado**. La página también debe figurar en Sitio → Páginas
   como «ESI — Inicio».
7. Edita un texto, guarda, recarga y comprueba que permanece. Prueba una imagen.
8. Despublica y abre `/esi` en incógnito: el visitante no debe ver el contenido.
   El diseñador debe poder acceder y volver a publicar. Repite entrando por `/`.
9. Publica y envía una asesoría de prueba. Debe crear una oportunidad CRM y mostrar
   confirmación. El formulario no admite envíos públicos con la página no visible.
10. Tras aprobar la prueba, aplica la misma actualización únicamente en ESIBOLIVIA.

Si la barra no cambia, comprueba que reiniciaste la instancia correcta y que la
versión instalada es 20.0.1.1.0. No aumentes permisos de usuarios para resolverlo.

## Edición y mantenimiento

El estado de publicación se conserva en actualizaciones futuras mediante
`noupdate` en el registro de página. La plantilla del módulo se actualiza para
aplicar esta corrección. Futuras actualizaciones de esa plantilla pueden
sobrescribir personalizaciones guardadas en su vista; respáldalas antes.

Cabecera y pie originales están dentro del contenido ESI. Se ocultan únicamente
la cabecera/pie públicos predeterminados de Odoo; la interfaz del editor permanece
bajo control nativo de Odoo.

No existe restricción por nombre de base en el código para permitir la prueba en
una copia. No instales el módulo en otras bases. Las rutas de inicio afectan a los
sitios de la base donde se instala: revisar antes de usarlo en una base multisitio.

## Formulario y recursos

Dependencias: website y crm Community. Crea oportunidades en la compañía del sitio
actual, sin vendedor/equipo asignado. Revisa CRM sin filtro «Mis oportunidades».
Incluye CSRF, validación, escape HTML, campo antirrobots y separación de 60 segundos
por sesión. No envía correos automáticamente y no requiere scripts de B12.
La caché de páginas se desactiva solo para las páginas basadas en esta vista,
porque contienen token CSRF y mensajes de sesión.

La fuente conserva Inter/system-ui del original; no se suministró una fuente Inter
local. No se crea un favicon. Dominio previsto: www.esibolivia-odoo.online.

## Verificación

Se comprobaron localmente sintaxis, estructura QWeb, aislamiento de CSS, rutas y
archivos del ZIP. Se contrastó la integración con el código público de Website de
Odoo en la rama master consultada. **No se ejecutó una instalación en tu versión
Odoo 20 ni una prueba real de editar/guardar/publicar.** Debe verificarse en la copia.
No se accedió ni se modificó ninguna base durante la preparación del archivo.
