# Reportes con jerarquía de matriz y sucursales — Odoo 20

## Instalar esta actualización

El ZIP incluye ocho módulos completos: esi_reportes_base_v20, esi_finanzas_v20, esi_ventas_report_v20, esi_compras_report_v20, esi_pos_report_v20, esi_produccion_report_v20, esi_kardex_v20 y esi_inventario_calzados_v20.

Reemplazar esas carpetas, reiniciar Odoo, actualizar primero Motor de reportes (esi_reportes_base_v20) y después los reportes instalados. No desinstalarlos. Si Kardex por talla aún no está instalado, instalarlo. Recargar el navegador con Ctrl+Shift+R. Abrir un informe nuevo para evitar conservar filtros antiguos de almacén.

## Selección de ámbito

- Seleccionar TOSSCANO GRUP incluye la matriz y todas sus sucursales descendientes autorizadas para el usuario, también niveles inferiores. No hace falta marcar individualmente cada sucursal en el selector superior.
- Una sucursal hoja consulta solo sus datos; nunca a la matriz ni a sus hermanas. Una sucursal intermedia incluye sus propias hijas autorizadas.
- La compañía debe estar asignada al usuario. El ámbito es la intersección entre la jerarquía seleccionada y las compañías asignadas. No incluye otras empresas, no usa sudo y conserva las demás reglas de registros. Esta actualización no otorga permisos nuevos ni cambia asignaciones de usuarios.
- La pantalla muestra Matriz y sucursales incluidas. Los filtros de almacenes, ubicaciones, documentos, productos y centros de trabajo permiten registros de ese ámbito. El servidor también valida el filtro.
- En Kardex por talla, Almacén es opcional y queda vacío al cambiar compañía. Vacío significa todos los almacenes accesibles de la jerarquía. Seleccionar uno restringe el informe a ese almacén y su sucursal. La matriz sin almacén no bloquea los almacenes de sus hijas.

## Reportes incluidos

- Finanzas: balance, resultados, sumas y saldos, mayor, CxC/CxP, caja/bancos, flujo, analítica, contactos, resumen e impuestos. Consolida los apuntes por ID de cuenta nativa compartida. El mayor identifica la sucursal. No mezcla monedas distintas. Es una suma de entidades autorizadas, no un proceso de eliminaciones intercompañía ni un cierre consolidado legal.
- Ventas, compras y POS: consulta los documentos de cada compañía y muestra su sucursal real res.company; se retiran los filtros automáticos del modelo antiguo esi.store que ocultaban documentos de sucursales nativas. Las reglas de acceso del servidor siguen vigentes.
- Producción: todos los modos existentes, incluidos centro actual, órdenes, tallas, costos, faltantes y destajos. Los filtros de OF, grupo y centro restringen a las compañías correspondientes.
- Kardex general: conserva valoración, períodos, saldos, separación/consolidación de almacenes y ancho completo. Calcula cada compañía de forma independiente antes de reunir las filas. Consolidar almacenes no mezcla costos de distintas compañías.
- Kardex por talla: une las columnas de tallas entre sucursales y muestra Sucursal / compañía y Moneda cuando reúne varias. Mantiene PU y valor de cada compañía; no promedia ni usa el costo de la matriz para sus hijas. Sigue mostrando existencias actuales, no movimientos históricos.
- Consultar, PDF y Excel comparten la misma selección jerárquica.

No reemplaza las reglas globales de compañías ni modifica documentos, cantidades, costos o asientos. Tampoco reemplaza módulos de terceros ni el funcionamiento de informes nativos ajenos a estos módulos ESI. Los comprobantes de una factura/asiento continúan perteneciendo a la compañía de ese documento.

## Validación

42 pruebas locales aprobadas: 11 de jerarquía/seguridad/despacho y columnas de talla; 16 de Kardex físico/valoración; 8 de matriz; 7 de centros de trabajo. Se comprobaron sintaxis Python, XML, manifiestos, campos de alcance en vistas y estructura del ZIP. Las pruebas de alcance usan un ORM simulado; no sustituyen instalación ni prueba completa en su servidor Odoo. No se accedió a la base del usuario.
