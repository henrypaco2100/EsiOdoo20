# Migración Tosscano v20 — 20.0.6.0.0

Datos de apertura con corte al **28/10/2026**, para una **base nueva**.

## Precios de venta — 20.0.6.0.0

Incluye precio de venta y listas Minorista/Mayorista en BOB, compartidas entre sucursales. **Importar datos** las carga automáticamente. En una base existente, usar **4. Cargar precios de venta y tarifas**, sin repetir saldos.

65 plantillas tienen precio por modelo para todas sus tallas. EL-V-02-06 queda pendiente por diferencia de código respecto a E-V-02. Donde falta mayorista, se usa minorista; se conservan las tres filas cuyo mayorista supera al minorista. Véase PRECIOS_Y_TARIFAS.md. No se cambian costos ni se interpreta la columna de costo como precio de venta.

## Tallas completas — actualización 20.0.5.1.0

Todas las líneas no infantiles incluyen las tallas 34 a 46, sin necesidad de saldo. Se conservan todas las tallas existentes. En este catálogo la línea infantil se identifica como **Escolar** (8 plantillas); mantiene sus tallas de origen. No se agrega stock ficticio: los saldos siguen sumando 6.449 pares.

En una base ya importada con corte 28/10, actualizar el módulo y pulsar **Completar tallas 34–46** en el registro existente. No repetir Importar saldos. Se crean las variantes faltantes y se les asignan los costos confirmados por compañía. Los marcadores conservan los costos posteriores ya procesados.

## Instalación y uso

Requiere `esi_calzados_v20` 20.0.11.2.0 o posterior y `esi_sucursales_v20`. Copiar la carpeta de este ZIP al directorio de addons, reiniciar Odoo e instalar el módulo. El ZIP incluye únicamente el módulo de migración.

Crear el registro y seleccionar TOSSCANO GRUP, Fábrica, CBBA y SCZ, con un almacén por sucursal. Las cuatro compañías deben usar BOB y el usuario debe tener acceso a ellas. Se requieren permisos de administración de Ajustes, Ventas, Inventario y Contabilidad; para recetas, Fabricación.

1. **Importar datos**: categorías, unidades, productos, plan contable, costos y configuración AVCO.
2. **Importar saldos**: cantidades de las nuevas hojas de inventario.
3. **Crear recetas (Fábrica)**: intenta crear las LdM completas y muestra las pendientes con su motivo en «Recetas en Fábrica». Puede repetirse sin duplicar las LdM vinculadas.

Las recetas siempre pertenecen a la compañía seleccionada en Fábrica, aunque los productos terminados sean globales. No se crean empresas ni almacenes. Actualizar el módulo no ejecuta importaciones automáticamente. No reutilizar un registro del corte anterior para cargar estos saldos sobre una base operativa.

## Contenido del corte

- 352 materias primas, exclusivas de Fábrica y con Componentes activo.
- 66 plantillas de terminados, 802 variantes, globales y con Fabricar activo.
- Categorías: **Materia prima → familia → subfamilia** y **Producto terminado → familia → subfamilia**.
- 13 unidades, 280 cuentas de origen y configuración AVCO/cuentas por compañía.
- Terminados: Fábrica **4.156 pares**, CBBA **1.874**, SCZ **419**; total **6.449 pares**.
- Valor fuente de terminados **Bs 982.397,53**; costos completos para todas las variantes con saldo. Son costos por par, no precios de venta. No se usa el total de una receta como costo de apertura.
- Código final 010 se unifica con 10 únicamente para los dos modelos confirmados. Planta Piloto sigue separada.
- HILO CAFÉ #20 repetido se importa una sola vez. Se conservan las correcciones confirmadas de códigos de cintas.
- Un saldo queda pendiente: **TEX-PEK-18-EST, −18 metros, costo cero**. No se convierte en cero ni en un saldo positivo.

## Fecha y valoración

El 28/10/2026 es el **corte del archivo fuente**. Los ajustes de inventario y costos se ejecutan con la fecha nativa de Odoo del día de importación. No se retrofechan movimientos ni capas de valoración. Por tanto, un informe histórico del 28/10 anterior a la ejecución no contendrá esta apertura.

Los marcadores impiden recargar aperturas ya aplicadas y sobrescribir después un promedio modificado por operaciones. Se omiten productos con existencias, reservas o movimientos previos incompatibles con una apertura. El detalle aparece en el resultado.

## Recetas recibidas

Incluye las **12 fichas militares** del último Excel, con 292 líneas fuente. Las cantidades se interpretan por par, incluso cuando la ficha tiene un lote mayor. Los costos de mano de obra y gastos se conservan como evidencia; no se inventan tiempos de operaciones.

**Con los archivos actuales, las 12 fichas quedan pendientes: no se crean LdM parciales.** Faltan equivalencias de materiales/unidades y hay códigos ambiguos o asociados a una sola talla. Véase `INCIDENCIAS_RECETAS.md`. Algunas fichas tampoco tienen producto terminado correspondiente en el catálogo recibido. El botón informa estas incidencias sin bloquear productos ni saldos. Resolver esas equivalencias requiere datos adicionales y una actualización de la correspondencia; no basta repetir el botón.

## Evidencia y validación

`data/direct.json` es la fuente normalizada actual. `source_20261028.json` conserva los inventarios nuevos; `recipes_20261028.json`, las fichas nuevas; `finished_costs.json`, procedencia de los costos. `source.json` conserva evidencia histórica del corte anterior y no alimenta la carga directa actual.

Se incluyen pruebas locales de datos y métodos con dobles ORM. No sustituyen una instalación real en Odoo ni una conciliación contable. No se accedió al servidor. Las referencias persistentes pertenecen a `tosscano_import_data`; no eliminarlas manualmente.

## AVCO y cuentas (versión 20.0.3.0.0)

Si ya importó, actualice el módulo y pulse **Configurar AVCO y cuentas** sobre su registro de migración. No necesita repetir importación de datos o saldos. En nuevas importaciones se ejecuta automáticamente después del plan contable y antes de cargar saldos.

Alcance: todas las categorías de los datos Tosscano, sus categorías padre y las categorías actuales de los productos vinculados. Configuración por compañía: matriz, fábrica, CBBA y SCZ. No cambia globalmente las categorías ajenas a la migración.

- Método: promedio ponderado (`average`, AVCO).
- Valoración: perpetua (`real_time`, al facturar).
- Cuentas de existencias: 1.1.3.01.01 para cueros/textiles/materias primas, 1.1.3.01.02 para otros materiales, 1.1.3.05.03 para terminados.
- Gastos: 5.0.1.01.01 y 5.0.1.01.02 para materiales; 5.0.1.01.90 para costo de venta de calzados terminados.
- Ingresos: cuenta comercial 4.0.0.01.08 en matriz; fábrica 4.0.0.01.06; CBBA 4.0.0.01.04; SCZ 4.0.0.01.05.
- Variaciones: 5.0.1.01.91, .92 y .93 según clase; se asignan en la cuenta de existencias, de la cual procede el campo relacionado de la categoría.
- Diferencias de precio: 5.0.1.01.94.
- Entregado pendiente de facturar: 1.1.3.99.01 (activo corriente).
- Facturado pendiente de entregar: 2.1.0.99.01 (pasivo corriente).
- Recibido pendiente de factura: 2.1.0.99.02 (pasivo corriente).
- Facturado pendiente de recibir: 1.1.3.99.02 (activo corriente).

Las cuentas pertenecen a TOSSCANO GRUP y las sucursales acceden mediante la jerarquía nativa. Se reutilizan cuentas activas de código y tipo compatibles; en su defecto, una coincidencia exacta de nombre/tipo; si falta, se crea. Si un código ya está ocupado por una cuenta incompatible, la nueva recibe un sufijo libre, sin cambiar la cuenta existente. El resultado muestra los códigos reales asignados. Diarios generales de valoración separados por compañía, sin reutilizar un diario de otra sucursal.

Las cuentas específicas de ingresos/gastos configuradas directamente en un producto pueden prevalecer sobre la categoría; se conservan. No se activa ni desactiva la contabilidad anglosajona. No se cambian impuestos ni se publican manualmente asientos para suplir documentos pendientes.

**Comportamiento Odoo 20:** Perpetual (at invoicing) contabiliza las compras y ventas al publicar facturas. Recepciones y entregas actualizan cantidades y valoración de inventario, pero no equivalen necesariamente a un asiento inmediato. Las cuentas transitorias sirven a las regularizaciones nativas de valoración/devengo al cierre. Completar estas cuentas no automatiza todos los cierres ni contabiliza retrospectivamente documentos. No se agrega un asiento por cada movimiento que duplique las facturas. Los ajustes/operaciones que admiten asiento directo dependen también de las cuentas de sus ubicaciones virtuales; esta versión no modifica dichas ubicaciones.

Si ya hay existencias, cambiar de costo estándar a AVCO invoca la lógica nativa de recalcular valoración y costo según el cierre y movimientos existentes. Repetir la configuración con el mismo método evita volver a escribir ese campo. Revisar el resultado en una copia de la base antes de producción.

Referencia oficial: https://www.odoo.com/documentation/20.0/applications/finance/accounting/get_started/inventory_valuation.html
Comprobado además contra el código nativo local de Odoo 20. Las pruebas locales no sustituyen pruebas de facturas, ajustes, devoluciones y fabricación en una instancia Odoo.


