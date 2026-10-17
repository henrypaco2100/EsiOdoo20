# Validación de esta entrega

- XML QWeb analizado correctamente con lxml.
- Python compilado sin errores de sintaxis; JavaScript validado con `node --check`.
- Manifest y rutas de todos los recursos comprobados.
- Fotografía y logotipo verificados como JPEG válidos.
- Once secciones y su orden contrastados con el HTML publicado de B12.
- Texto de las diez secciones ajenas al formulario comparado automáticamente:
  coincide con la versión publicada consultada.
- Todas las anclas internas apuntan a identificadores existentes.
- Recursos de imagen locales, sin scripts B12 ni reCAPTCHA B12.
- Formulario con token CSRF y validación explícita de campos en servidor.
- Validador: caso válido, correo inválido, nombre vacío, rubro no permitido y
  mensaje excesivo; comprobación de escape HTML.

## Pendiente, obligatorio antes de producción

No se dispone de Odoo 20 ejecutándose en este entorno. No se ha instalado el
módulo, compilado su paquete con Odoo, renderizado QWeb mediante Odoo ni creado
una oportunidad en una base real. La validación sintáctica no certifica esos pasos.

La prueba visual automatizada local no se pudo ejecutar porque no está instalado
el ejecutable Chromium. No se certifica una comparación visual píxel a píxel.
Los estilos responsive originales se conservan; verificar escritorio y móvil
siguiendo README, incluida la visualización del logotipo.

La prueba integral en copia de ESIBOLIVIA debe comprobar también el backend,
la reversión por desinstalación y cualquier tema/módulo existente con rutas `/`.
