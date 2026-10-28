# Migración Tosscano v20 — 20.0.3.1.0

## Uso

1. Actualizar este módulo en Odoo (reiniciar el servicio antes de actualizar). Si es la primera instalación, instalarlo desde Aplicaciones.
2. Abrir **Migración Tosscano → Importar Tosscano**. Seleccionar TOSSCANO GRUP, FABRICA CALZADO, CBBA y SCZ, y el almacén de cada sucursal. Activar esas cuatro compañías. El usuario necesita administración de Inventario y Contabilidad, además de Ajustes. Los importes fuente están en BOB.
3. Pulsar **1. Importar datos**. No exige revisar filas ni asignar unidades una por una.
4. Pulsar **2. Importar saldos**. El resultado indica qué se cargó y qué no se pudo aplicar. Los casos pendientes pueden corregirse manualmente y luego repetir el botón: no duplica saldos ya aplicados. Los terminados sin costo ahora se cargan con valor cero y advertencia.

## Datos incluidos

- 348 materias primas/artículos de catálogo: lista oficial corregida con la fotografía y materiales adicionales de Kardex. Exclusivos de FABRICA CALZADO. Componentes activos excepto herramientas. El duplicado idéntico de HILO CAFÉ #20 se consolida.
- Categorías nativas **Familia → Subfamilia**. No se añaden campos Familia/Subfamilia al producto. Las columnas técnicas de la versión anterior se conservan únicamente para compatibilidad con su registro histórico; ya no son un paso del flujo.
- 13 unidades normalizadas: UNIDAD, PAR, METRO, M2, PIE2, GRAMO, KG, LITRO, ROLLO, CONO, BOTE, LATA, PAQUETE. Reutiliza unidades físicas nativas. Convierte PIE2 con 0,09290304 m². Un cono/rollo/lata/bote/paquete se crea como unidad independiente, sin inventar capacidad. METROS/M/metro, uni/unidad, ft2/pie2, gr/gramo se normalizan.
- 68 plantillas de terminados y 357 variantes por talla, compartidas entre sucursales. Provienen de las tres hojas de inventario disponibles, pues el archivo llamado lista productos terminado contiene el mismo libro que las recetas. No se afirma que este catálogo provisional cubra productos ausentes de esas hojas.
- Atributos Talla, Color y Modelo. Forro, Material y Acabado se incluyen cuando aparecen explícitos en la descripción. No se inventa material para productos cuya descripción no lo especifica. Modelo toma el código de familia/modelo del origen.
- Se conserva una plantilla por código de origen y versión; el color es un valor de atributo en esa plantilla y las tallas son sus variantes. No se unifican todos los colores en una plantilla ni se generan combinaciones de colores/tallas inexistentes. Las versiones Planta Piloto con código reutilizado se separan con sufijo PILOTO.
- Terminados categorizados por línea MILITAR/ESCOLAR/INDUSTRIAL/OTROS y subcategoría modelo. Los materiales adicionales de Kardex recuperan familia y subfamilia de su hoja CATALOGO MP; todos quedan categorizados. Las categorías pueden corregirse manualmente.
- 280 cuentas del archivo con su jerarquía en la matriz. Conserva la clasificación y estado activo del archivo, que incluye 26 observaciones pendientes de criterio contable. Configura las cuentas de categorías y diarios de valoración; no configura impuestos ni conciliaciones iniciales. Si una cuenta ya existe con código y tipo compatible, la vincula sin sobrescribirla; inconsistencias se listan.

## Saldos y costos

- Materias primas: fuente RESUMEN/Kardex, corte 23/10/2026. Terminados: hojas por almacén, 6.402 pares en total (Fábrica 3.840, CBBA 2.141, SCZ 421).
- Usa ajustes nativos de inventario, en la ubicación principal del almacén. No modifica manualmente valoración, movimientos ni asientos. Los movimientos tienen la fecha real de ejecución; el 23/10/2026 queda como referencia del origen.
- Para materiales usa el costo unitario de Kardex cuando está disponible; al crear el catálogo conserva el costo de catálogo como referencia inicial. Para terminados no se inventa costo histórico a partir de una receta estimada. **Los terminados con costo cero se cargan por talla y almacén**, conservando una advertencia histórica de valoración pendiente. Las materias primas sin costo válido siguen pendientes. Tampoco se cambia el costo si hay movimientos/existencias previas.
- Omite productos con movimientos, existencias, reservas o conteos previos, en vez de reemplazar su stock de producción. Repetir no aplica dos veces una apertura. No sobrescribe saldos ya importados para corregirlos: las correcciones posteriores son ajustes nativos manuales.
- Ocho filas con códigos corregidos ambiguos tienen cantidad cero en RESUMEN y no generan ajustes. El HILO CAFÉ #20 duplicado no se suma dos veces. La evidencia completa sigue incluida en data/source.json y direct.json.

## Recetas

El botón intenta crear recetas compartidas por talla únicamente cuando todos los componentes tienen correspondencia y unidad compatibles. Las 12 fichas disponibles aún contienen códigos faltantes, conversiones de envases sin capacidad, bolsa/numeración mezcladas y consumos talla 40; se listan como pendientes y **no se crean recetas incompletas**. La importación del catálogo y del plan no queda bloqueada por estas incidencias. No se inventan tiempos por centro a partir de costos de mano de obra.

## Compatibilidad y validación

Requiere esi_calzados_v20 20.0.11.2.0 o posterior, esi_sucursales_v20, Inventario y Contabilidad. Este ZIP contiene únicamente migrar_tosscano_v20. No reemplaza los otros módulos.

Validación local: 32 pruebas de integridad de datos/código, Python y XML comprobados. La instalación y ejecución completas en una base Odoo 20 están pendientes de prueba. No se accedió al servidor de producción. Probar primero en una copia: no se presenta como una migración ya ejecutada ni financieramente conciliada.

Las referencias de datos importados usan un espacio persistente propio para que desinstalar la herramienta no intente eliminar cuentas o productos importados. No borrar esos identificadores externos manualmente. No hay asistente de reversión de ajustes ya aplicados.


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
Comprobado además contra el código nativo local de Odoo 20. Las 32 pruebas locales no sustituyen pruebas de facturas, ajustes, devoluciones y fabricación en una instancia Odoo.


## Corrección de saldos terminados — 20.0.3.1.0

La versión anterior omitía todos los saldos positivos de terminados cuyo costo era cero. Esta versión permite aplicar sus cantidades con costo cero mediante el ajuste nativo, sin sustituirlo por un costo estimado de receta.

Para recuperar saldos omitidos: actualizar el módulo (reiniciar Odoo antes), abrir el registro existente y pulsar **2. Importar saldos**. No repetir Importar datos. Se conservan los marcadores de cargas anteriores y no se vuelven a cargar. Los materiales previamente importados permanecen intactos. La pantalla informa las cantidades de terminados aplicadas por sucursal en esta ejecución.

Origen esperado completo: Fábrica 3.840 pares, CBBA 2.141 y SCZ 421; total 6.402. Son totales de origen, no garantía de que se apliquen todos si hay movimientos/existencias previas, referencias faltantes u otras incompatibilidades. Esos casos se detallan en el resultado.

Los productos con costo positivo en la sucursal conservan ese costo. Si no hay costo, la cantidad aumenta pero la valoración inicial será cero. **La carga de cantidades no completa el saldo contable de apertura**: posteriormente hay que regularizar la valoración mediante las herramientas nativas con los costos reales. Repetir Importar saldos no revaloriza ni vuelve a introducir las cantidades ya cargadas. La advertencia guardada documenta el estado al importar; no se borra automáticamente al modificar costos.

Validación: 32 pruebas locales, incluidas ocho que ejecutan el método real de importación con modelos simulados: terminado sin costo, costo existente, sucursales, agregación de filas, repetición, movimientos previos, materiales sin costo y costo negativo. No se ejecutaron en una instancia Odoo ni sustituyen una conciliación de inventario/contabilidad.
