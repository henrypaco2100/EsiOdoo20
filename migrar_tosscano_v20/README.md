# Migración Tosscano v20 — 20.0.4.0.0

## Actualizar una base ya importada

1. Sustituir la carpeta `migrar_tosscano_v20`, reiniciar Odoo y actualizar el módulo desde Aplicaciones. No desinstalarlo.
2. Abrir el registro de migración existente; activar matriz, Fábrica, CBBA y SCZ.
3. Pulsar **Actualizar códigos y costos de terminados**. Aplica los PU confirmados a todas las tallas vinculadas en las tres sucursales y matriz. No es necesario volver a importar cantidades.
4. Solo si quedaron saldos sin cargar anteriormente, pulsar **2. Importar saldos**. Los marcadores persistentes impiden duplicar aperturas.

Actualizar el módulo no ejecuta automáticamente la importación ni cambia costos en la base. La acción explícita utiliza el registro y compañías elegidos. Requiere administrador de Ajustes, Inventario y Contabilidad.

## Base nueva

Seleccionar TOSSCANO GRUP, sus tres sucursales directas FABRICA CALZADO, CBBA, SCZ y un almacén por sucursal. Todas deben usar BOB. Pulsar **1. Importar datos** y después **2. Importar saldos**. Los PU confirmados se aplican automáticamente al importar datos y antes de cargar cada saldo nuevo. No se crean empresas ni almacenes.

## Costos y códigos confirmados

- Los 30 costos antes pendientes están completos; se suman a los 34 códigos con PU en INVENTARIO FABRICA.xlsx. Se conserva la procedencia por celda en `data/finished_costs.json`.
- Códigos oficiales **M-W-01-10** y **M-BT-01-10**, equivalentes a los anteriores terminados en 010. No se normalizan otros códigos por semejanza.
- Nueva carga: 66 plantillas y 352 variantes, después de unificar las dos equivalencias. Planta Piloto permanece separada: su costo es 152 según la fuente, igual al producto normal.
- Cantidades fuente: Fábrica 3.840, CBBA 2.141, SCZ 421; total 6.402 pares. Valor fuente total **Bs 972.235,64**, desglosado en COSTOS_APERTURA.md. No equivale a saldo contable ya cargado.
- Los importes son **costos unitarios por par**, no precios de venta. No se modifica `list_price`. No se toman importes de recetas como costos de apertura.
- `standard_price` se escribe por variante con `with_company`. Odoo genera su ajuste nativo de valoración, con cantidad actual y fecha de ejecución. No se cambia SQL de valoración, no se retrofechan movimientos y no se recalcula el costo histórico de ventas ya realizadas.
- La acción tiene un marcador por producto, compañía y precio de esta revisión. Repetir no vuelve a revalorizar ni sobrescribe el promedio que pudiera cambiar después por compras/fabricación. Un nuevo PU distinto sí constituye una nueva revisión.
- Los informes y costos de componentes que lean el costo nativo obtienen el valor de su compañía. No se reemplazan informes nativos ni sus datos históricos.

### Compatibilidad con códigos ya importados

Si solo existe una plantilla vinculada (010 o 10), se reutiliza; se añaden las tallas que falten y sus referencias pasan al código oficial. Los identificadores técnicos antiguos se conservan como equivalencias internas, incluso para LdM y marcadores de saldos: no se duplica una apertura por el cambio de código.

Si una versión anterior ya creó **las dos plantillas distintas**, se informa de sus IDs y se omite su consolidación y carga adicional de cantidades. Los PU sí se actualizan en ambas. No se eliminan productos ni se trasladan automáticamente movimientos, reservas, recetas o documentos contabilizados. Este caso requiere una consolidación específica sobre la base y no queda resuelto por renombrar productos. Si otro producto ajeno ocupa una referencia oficial, la transacción se detiene con un mensaje, sin crear una referencia duplicada.

El historial de cargas antiguas sin costo se conserva como evidencia; no es un indicador del costo actual. El resultado de la nueva acción describe la actualización aplicada.

## Datos y reglas que se conservan

- 348 materiales/artículos del catálogo, solo en Fábrica, todos con **Componentes** activo. Terminados universales con **Fabricar** activo.
- Categorías nativas Familia → Subfamilia. Tipo y Medida son campos propios; Familia/Subfamilia no se crean como campos del producto.
- 13 unidades: UNIDAD, PAR, METRO, LITRO, KG, GRAMO, M2, PIE2, ROLLO, CONO, BOTE, LATA, PAQUETE. PIE2 equivale a 0,09290304 m². PAR representa un par. No se inventan capacidades de envases.
- Atributos Talla, Modelo y Color; Forro, Acabado y Material solo cuando figuran explícitamente en la descripción. No se crean combinaciones inexistentes de color/talla.
- 280 cuentas de origen con jerarquía en matriz, incluidas sus observaciones y estado. Categorías AVCO y cuentas por compañía, descritas debajo.
- Stock de materiales desde RESUMEN/Kardex; terminado desde las tres hojas de sucursal. Ajustes nativos a fecha de ejecución con referencia al corte 23/10/2026.
- No se sobrescriben cantidades de productos con movimientos/existencias/conteos/reservas previas. Se preservan los marcadores de aperturas aplicadas.
- El HILO CAFÉ #20 idéntico se consolida y su saldo no se suma dos veces. Las ocho filas ambiguas con cantidad cero siguen documentadas.
- `data/source.json` conserva evidencia original, incluidos códigos antiguos: no es la fuente operativa de los costos nuevos. `direct.json` contiene los datos normalizados actuales.

## Recetas

Las 12 fichas se conservan. La importación solo crea una receta cuando TODOS los componentes tienen correspondencia única y unidad compatible. Persisten las incidencias anteriores: códigos de materiales ausentes, conversiones de envases sin capacidad, bolsa/numeración mezcladas y componentes de talla 40. La actualización de PU no resuelve esas incidencias ni crea recetas incompletas. El resultado enumera las recetas pendientes. Los importes de mano de obra no se convierten en minutos inventados.

## Compatibilidad y pruebas

Requiere esi_calzados_v20 20.0.11.2.0 o posterior y esi_sucursales_v20. El ZIP contiene únicamente migrar_tosscano_v20 actualizado; no reemplaza los módulos de calzados, sucursales ni reportes existentes.

41 pruebas locales aprobadas: conservación de cantidades, cobertura de costos, referencias/categorías/unidades, equivalencias, marcadores de saldos, cambios nativos de costo por compañía y repetición después de cambiar AVCO. Las pruebas de ejecución usan dobles ORM, no una instancia real de Odoo. Python/XML y estructura del ZIP verificados. No se accedió ni instaló nada en el servidor. La instalación y conciliación contable deben verificarse en una copia de la base.

Las referencias persistentes pertenecen a `tosscano_import_data`. No eliminarlas manualmente. La herramienta no revierte automáticamente ajustes ya aplicados.

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


