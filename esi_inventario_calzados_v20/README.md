# Kardex por talla — Odoo 20

Instalar `esi_inventario_calzados_v20` junto a los módulos existentes `esi_calzados_v20` y `esi_reportes_base_v20`. Copiar la carpeta, reiniciar Odoo, actualizar la lista de aplicaciones e instalar. No sustituye el reporte de producción ni la migración.

Acceso: **Inventario → Reportes → Kardex por talla** (administrador de Inventario). Seleccionar sucursal, almacén y opcionalmente categoría/producto. Pulsar Consultar, Excel o PDF.

Columnas: Código, Descripción, Unidad, PU, TOTAL, tallas ordenadas y Valor. Conserva columnas de tallas sin saldo dentro del catálogo filtrado. Una fila por plantilla y combinación de atributos distintos de Talla. Colores/modelos/materiales distintos y versiones Planta Piloto no se mezclan.

- Solo productos almacenables marcados Fabricar; categoría inicial Producto terminado, si existe, incluyendo todos sus descendientes.
- Cantidades actuales de ubicaciones internas del almacén seleccionado. Suma quants por variante, incluidos lotes/paquetes, sin duplicar. Excluye mercancía de terceros con propietario y tránsito externo.
- Existencia física o disponible sin reservas. Incluye cantidades negativas; las filas totalmente a cero se ocultan salvo que marque Incluir productos sin existencias. Productos sin atributo de talla se muestran en Sin talla.
- PU es costo actual de cada variante en la sucursal, no precio de venta. Si las tallas tienen costos distintos, muestra Variable y calcula Valor como suma(cantidad × costo) por variante. Si se consulta disponible, Valor corresponde a esa cantidad disponible, no a la valoración total de inventario.
- Totales separados por unidad. No se convierten pares a unidades ni se suman unidades incompatibles. Los códigos ESI con sufijo -T40 se muestran sin el sufijo de talla; los demás códigos se conservan.
- No consulta a una fecha pasada. El informe indica fecha/hora actual de consulta y moneda de la compañía. Cada exportación vuelve a consultar stock, por lo que cambios entre consultas pueden modificar los resultados.
- Sin sudo ni SQL directo: respeta permisos y reglas de registros, exige sucursal activa y verifica que el almacén pertenezca a ella. La selección es una sola sucursal/almacén por informe.
- Excel con encabezado fijo, filtros y orientación horizontal. PDF A3 horizontal; para más de 24 tallas, usar Excel o filtrar producto.

Validación: 8 pruebas locales de la matriz (tallas, totales, negativos, costos variables, separación de atributos/unidades y cero), sintaxis Python/XML y ZIP. No probado mediante instalación en un servidor Odoo 20 ni con renderizador PDF real. No modifica productos, costos, saldos o movimientos.
