# ESI Kardex físico · Odoo 20

Módulo: `esi_kardex_v20`, versión 20.0.1.0.0. Autor: ESI. LGPL-3.

## Qué conserva del reporte anterior

- Compañía y rango de fechas, interpretado en la zona horaria del usuario.
- Uno o varios almacenes; filtros opcionales de ubicaciones y sus descendientes.
- Productos/variantes, categorías y subcategorías, lotes o series.
- Saldo inicial, entradas, salidas y saldo final por producto.
- Detalle cronológico o resumen, separación por almacén o consolidado.
- Variantes separadas o agrupadas por plantilla; orden por categoría.
- Documento, origen, lote y ubicaciones en las líneas detalladas.
- Cantidades en la unidad del producto y columnas equivalentes en otras unidades.
- Vista en pantalla, Excel y acción PDF horizontal A3.

## Solo consulta de inventario

Lee líneas realizadas (`stock.move.line`, estado `done`), su fecha nativa y la
cantidad almacenada en la unidad del producto (`quantity_product_uom`).
No hereda ni modifica stock.move, stock.move.line, stock.quant, productos,
contabilidad ni modelos de valoración. No escribe costos ni fechas, no confirma
operaciones y no calcula FIFO/AVCO. Los únicos datos que guarda son los filtros,
la vista previa y el Excel en un asistente temporal propio.

Es un Kardex **físico**, no valorado. No contiene costo unitario, saldo monetario,
revalorizaciones ni distribución inventada de costos entre almacenes. La valoración
permanece en los informes nativos de Odoo. El módulo anterior esi_st_kardex de
Odoo 13 NO es una dependencia y no debe instalarse en Odoo 20.

## Ubicación e instalación

Copiar esi_kardex_v20 a la ruta personalizada de addons, reiniciar Odoo 20,
actualizar la lista de aplicaciones y quitar el filtro «Aplicaciones» para buscar
«ESI - Kardex físico por almacén». Instalarlo. No requiere reinstalar los demás
módulos ni modificar MuK. Requiere stock, web y la librería xlsxwriter.

Menú: **Inventario → Reportes → Kardex físico ESI** (puede aparecer como Informes).
No crea una aplicación ni un acceso raíz en la barra lateral. Disponible para el
rol Administrador de Inventario, como el menú nativo de Reportes. No eleva
permisos: respeta compañías activas y reglas de acceso del usuario.

## Cómo interpretar los saldos

- Saldo inicial: neto de todos los movimientos realizados anteriores a Desde.
- Fechas del período: Desde 00:00 hasta el día siguiente a Hasta, excluido.
- Saldo final: inicial + entradas - salidas; conserva saldos negativos.
- Incluye ubicaciones internas de los almacenes, incluso recepción/expedición
  cuando su uso nativo es interno. Excluye ubicaciones de tránsito.
- Un traslado dentro del mismo ámbito de consulta no cambia sus existencias:
  no genera entrada/salida en este Kardex. Filtre por ubicación si necesita ver
  los cruces de su perímetro. No es una lista de todos los movimientos internos.
- Separado por almacén: un traslado directo A→B muestra salida en A y entrada en B.
  Consolidado A+B: ese traslado se omite porque el saldo conjunto no cambia.
- En transferencias por tránsito, la salida de A y la recepción en B pueden tener
  fechas distintas: la mercancía en tránsito queda fuera hasta la recepción.
- Terceros: por defecto excluye las líneas con propietario asignado. Desmarcar
  «Excluir existencias de terceros» incluye también cantidades de consignación.
- Los filtros de lotes/productos/categorías afectan al saldo inicial y al período.
- Al agrupar variantes, suma solamente las variantes seleccionadas; sin filtro,
  incluye todas las variantes con movimientos que cumplan las condiciones.
- No presenta totales globales de cantidades entre unidades/productos diferentes.
- En detalle, SALDO INICIAL y RESUMEN DEL PRODUCTO son filas informativas;
  no sumar todas las filas de la hoja, porque el resumen repite los totales.
- Productos sin ningún movimiento histórico dentro del ámbito no generan fila.

## Unidades de medida

La unidad base siempre es la del producto. Las unidades adicionales producen
columnas Inicial/Entrada/Salida/Saldo. Deben compartir la misma referencia raíz
según relative_uom_id de Odoo 20. Ejemplo: Unidad → Caja de 12 → Paquete.
No convierte kilogramos a unidades ni aplica un factor supuesto. Si las unidades
no están relacionadas, esas celdas quedan vacías. Se usa la configuración actual
de unidades de Odoo; no se reconstruyen factores históricos modificados.
Excel y pantalla admiten varias unidades; PDF admite una adicional para mantener
la legibilidad. Para informes anchos o extensos, usar Excel.

## Límites y validación

El saldo depende de que el historial de movimientos esté completo. No reconstruye
existencias antiguas que se hubieran importado sin movimientos de apertura.
No concilia moneda ni contabilidad. Una consulta parcial por permisos muestra
solo la información accesible. Máximo 100.000 líneas históricas por consulta;
al excederlo pide reducir el conjunto de productos/categorías/almacenes, sin
recortar silenciosamente el saldo inicial.

Validado: sintaxis Python, XML contra esquema oficial Odoo 20, referencias de
campos y menú nativos consultadas en el código oficial; nueve pruebas aritméticas
con saldo inicial, fechas límite, traslados, devoluciones, ajuste, separación de
productos, orden estable, negativos y ausencia de datos.

No se ejecutó una instalación real de este nuevo módulo en Odoo ni un render PDF
con el motor del servidor. Antes de usarlo operativamente, instalar en pruebas y
comprobar un producto conocido: apertura 10, ingreso 5, salida 3 → saldo 12;
traslado 4 de A a B → A=8, B=4, consolidado=12. Comparar en iguales ubicaciones,
compañía, propietario y fecha con el historial nativo de Odoo.

Prueba aritmética reproducible:
`python3 esi_kardex_v20/tests/test_balances_standalone.py`

## Filtros más claros y dinámicos

1. **Período y productos**: compañía, período rápido (Hoy, Este mes, Mes anterior,
   Últimos 30 días o Elegir fechas), tipo de informe, almacenes, categorías y productos.
2. **Más filtros y presentación**: ubicaciones, lotes/series, terceros, agrupaciones
   y unidades adicionales.

Las fechas son editables al elegir Elegir fechas. Las ubicaciones disponibles se
adaptan a los almacenes; los productos, a las categorías; y los lotes, a los
productos y categorías. Al cambiar almacenes o productos se retiran selecciones
que dejan de ser compatibles. Los filtros activos se resumen antes del resultado
y se incluyen en pantalla/PDF y en una hoja separada del Excel.

Al cambiar filtros se limpia el resultado anterior; pulsar Consultar Kardex para
regenerarlo. Limpiar filtros restablece este mes, todas las selecciones vacías,
existencias propias y vista detallada, conservando la compañía seleccionada.
Los períodos rápidos se resuelven al seleccionarlos; las fechas visibles indican
el intervalo exacto utilizado.

Pruebas adicionales de métodos con API Odoo simulada: cuatro períodos rápidos,
raíz de unidades, escape de HTML y generación real de XLSX con hoja de filtros
(sin fórmulas inyectadas desde nombres). No sustituyen la validación en Odoo.
