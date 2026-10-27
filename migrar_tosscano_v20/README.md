# Migración Tosscano v20 — 20.0.2.0.0

## Uso

1. Actualizar este módulo en Odoo (reiniciar el servicio antes de actualizar). Si es la primera instalación, instalarlo desde Aplicaciones.
2. Abrir **Migración Tosscano → Importar Tosscano**. Seleccionar TOSSCANO GRUP, FABRICA CALZADO, CBBA y SCZ, y el almacén de cada sucursal. Activar esas cuatro compañías. El usuario necesita administración de Inventario y Contabilidad, además de Ajustes. Los importes fuente están en BOB.
3. Pulsar **1. Importar datos**. No exige revisar filas ni asignar unidades una por una.
4. Pulsar **2. Importar saldos**. El resultado indica qué se cargó y qué no se pudo aplicar. Los casos pendientes pueden corregirse manualmente en productos y luego repetir el botón: no duplica saldos ya aplicados.

## Datos incluidos

- 348 materias primas/artículos de catálogo: lista oficial corregida con la fotografía y materiales adicionales de Kardex. Exclusivos de FABRICA CALZADO. Componentes activos excepto herramientas. El duplicado idéntico de HILO CAFÉ #20 se consolida.
- Categorías nativas **Familia → Subfamilia**. No se añaden campos Familia/Subfamilia al producto. Las columnas técnicas de la versión anterior se conservan únicamente para compatibilidad con su registro histórico; ya no son un paso del flujo.
- 13 unidades normalizadas: UNIDAD, PAR, METRO, M2, PIE2, GRAMO, KG, LITRO, ROLLO, CONO, BOTE, LATA, PAQUETE. Reutiliza unidades físicas nativas. Convierte PIE2 con 0,09290304 m². Un cono/rollo/lata/bote/paquete se crea como unidad independiente, sin inventar capacidad. METROS/M/metro, uni/unidad, ft2/pie2, gr/gramo se normalizan.
- 68 plantillas de terminados y 357 variantes por talla, compartidas entre sucursales. Provienen de las tres hojas de inventario disponibles, pues el archivo llamado lista productos terminado contiene el mismo libro que las recetas. No se afirma que este catálogo provisional cubra productos ausentes de esas hojas.
- Atributos Talla, Color y Modelo. Forro, Material y Acabado se incluyen cuando aparecen explícitos en la descripción. No se inventa material para productos cuya descripción no lo especifica. Modelo toma el código de familia/modelo del origen.
- Se conserva una plantilla por código de origen y versión; el color es un valor de atributo en esa plantilla y las tallas son sus variantes. No se unifican todos los colores en una plantilla ni se generan combinaciones de colores/tallas inexistentes. Las versiones Planta Piloto con código reutilizado se separan con sufijo PILOTO.
- Terminados categorizados por línea MILITAR/ESCOLAR/INDUSTRIAL/OTROS y subcategoría modelo. Los materiales adicionales de Kardex recuperan familia y subfamilia de su hoja CATALOGO MP; todos quedan categorizados. Las categorías pueden corregirse manualmente.
- 280 cuentas del archivo con su jerarquía en la matriz. Conserva la clasificación y estado activo del archivo, que incluye 26 observaciones pendientes de criterio contable. No configura impuestos, diarios, conciliaciones iniciales ni contrapartidas de categorías. Si una cuenta ya existe con código y tipo compatible, la vincula sin sobrescribirla; inconsistencias se listan.

## Saldos y costos

- Materias primas: fuente RESUMEN/Kardex, corte 23/10/2026. Terminados: hojas por almacén, 6.402 pares en total (Fábrica 3.840, CBBA 2.141, SCZ 421).
- Usa ajustes nativos de inventario, en la ubicación principal del almacén. No modifica manualmente valoración, movimientos ni asientos. Los movimientos tienen la fecha real de ejecución; el 23/10/2026 queda como referencia del origen.
- Para materiales usa el costo unitario de Kardex cuando está disponible; al crear el catálogo conserva el costo de catálogo como referencia inicial. Para terminados no se inventa costo histórico a partir de una receta estimada. **Los saldos positivos sin costo quedan pendientes**: completar el costo de cada producto en la sucursal y repetir Importar saldos. Tampoco se cambia el costo si hay movimientos/existencias previas.
- Omite productos con movimientos, existencias, reservas o conteos previos, en vez de reemplazar su stock de producción. Repetir no aplica dos veces una apertura. No sobrescribe saldos ya importados para corregirlos: las correcciones posteriores son ajustes nativos manuales.
- Ocho filas con códigos corregidos ambiguos tienen cantidad cero en RESUMEN y no generan ajustes. El HILO CAFÉ #20 duplicado no se suma dos veces. La evidencia completa sigue incluida en data/source.json y direct.json.

## Recetas

El botón intenta crear recetas compartidas por talla únicamente cuando todos los componentes tienen correspondencia y unidad compatibles. Las 12 fichas disponibles aún contienen códigos faltantes, conversiones de envases sin capacidad, bolsa/numeración mezcladas y consumos talla 40; se listan como pendientes y **no se crean recetas incompletas**. La importación del catálogo y del plan no queda bloqueada por estas incidencias. No se inventan tiempos por centro a partir de costos de mano de obra.

## Compatibilidad y validación

Requiere esi_calzados_v20 20.0.11.2.0 o posterior, esi_sucursales_v20, Inventario y Contabilidad. Este ZIP contiene únicamente migrar_tosscano_v20. No reemplaza los otros módulos.

Validación local: 18 pruebas de integridad de datos/código, Python y XML comprobados. La instalación y ejecución completas en una base Odoo 20 están pendientes de prueba. No se accedió al servidor de producción. Probar primero en una copia: no se presenta como una migración ya ejecutada ni financieramente conciliada.

Las referencias de datos importados usan un espacio persistente propio para que desinstalar la herramienta no intente eliminar cuentas o productos importados. No borrar esos identificadores externos manualmente. No hay asistente de reversión de ajustes ya aplicados.
