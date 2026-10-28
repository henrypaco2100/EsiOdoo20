# Kardex físico y valorado — 20.0.4.0.0

Actualizar el módulo existente esi_kardex_v20 después de reemplazar su carpeta y reiniciar Odoo. Requiere stock_account. Menú Inventario → Reportes → Kardex físico y valorado.

Conserva filtros de fechas, sucursal, almacenes, categorías, productos, lotes, ubicaciones, unidades adicionales y agrupaciones. Mostrar valoración está activo por defecto. Sin valoración se conserva el reporte de cantidades.

Valoración de solo lectura:
- Valores de entrada/salida desde stock.move.value, repartidos según la cantidad nativa de cada línea, sin duplicar importes en movimientos con múltiples lotes/líneas. Un valor nativo cero se conserva como cero.
- En transferencias internas no valoradas por movimiento se utiliza el costo medio nativo a la fecha de la transferencia.
- Saldo inicial/final: cantidad del ámbito filtrado por el costo medio nativo del producto en la compañía al corte correspondiente. Usa avg_cost con to_date y una sola compañía activa en el contexto; incorpora los ajustes nativos product.value. No usa el costo actual para simular un costo histórico.
- Por almacén, ubicación o lote, esta es una asignación proporcional al costo medio de compañía, no una identificación de capas FIFO o costos específicos de un lote. La base se indica en pantalla y exportaciones. No debe confundirse con un mayor contable ni una valorización independiente por lote.
- Se muestra separado el ajuste necesario entre saldo inicial + entradas - salidas y valor al corte. Incluye cambios de costo, redistribución del costo medio entre almacenes y revisiones nativas de valores; no se presenta todo el ajuste como un nuevo movimiento físico.
- El importe actual guardado en un movimiento puede reflejar correcciones posteriores de Odoo. Es un informe calculado con la información nativa disponible, no una copia inmutable de un cierre anterior.
- Para valoración se excluye mercancía de terceros. Para incluir consignación, desactivar Mostrar valoración. Se excluye tránsito igual que en el reporte físico anterior.
- Máximo 3.000 líneas históricas por consulta valorada para limitar cálculos de cortes; filtrar por producto/categoría si se excede. Consulta física hasta 100.000 líneas. Nunca trunca saldos.

Interfaz: resumen de filtros fuera de la cuadrícula estrecha, a ancho completo. Formulario sin el límite de ancho de la hoja. Resultado con desplazamiento horizontal para todas las columnas. Excel y PDF usan los mismos datos; PDF A3 horizontal.

No escribe costos, movimientos, valoraciones ni asientos. Solo guarda la vista previa y archivo exportado del asistente. Mantiene reglas de acceso y validación de compañía/propietario del informe.

Validación: 16 pruebas locales (9 físicas y 7 de valoración), Python/XML y estructura de paquete. No instalado en una instancia Odoo ni renderizado el PDF real. Verificar actualización y resultados en la base de pruebas.
