# Migración Tosscano v20 — primera etapa

Versión 20.0.1.0.0. Este módulo es una herramienta de preparación y carga controlada de materias primas. No es todavía una migración integral ejecutable de inventarios, recetas y contabilidad.

## Configuración acordada

- Matriz: TOSSCANO GRUP.
- Sucursales directas: FABRICA CALZADO, CBBA y SCZ; un almacén seleccionado por sucursal.
- Saldo autorizado: RESUMEN/Kardex. Corte: 23/10/2026.
- Productos terminados: compartidos, sin compañía. Pendientes de catálogo correcto.
- Materias primas: compañía FABRICA CALZADO.
- Plan contable: preparado para la matriz, con acceso por jerarquía nativa; no se replica por sucursal.

## Qué funciona en esta versión

1. Aplicación «Migración Tosscano», visible para administradores.
2. Configuración explícita de compañías y almacenes existentes. Valida jerarquía y compañía del almacén. No crea entidades por coincidencia de nombre.
3. «Preparar datos de origen» carga una zona de revisión persistente y repetible sin duplicar filas:
   - 297 filas de materias primas.
   - 280 cuentas contables.
   - 342 saldos de RESUMEN/Kardex de materiales.
   - 484 saldos no nulos de terminados por sucursal/talla.
   - 12 recetas, con sus 292 componentes y observaciones.
   - 1 incidencia de catálogo terminado ausente.
4. Correcciones de códigos, medidas y colores de la fotografía del 27/10/2026, aplicadas a filas concretas de catálogo. Conserva valor original y propuesta. No cambia globalmente los códigos ambiguos en Kardex o recetas.
5. Importación individual o múltiple de materias primas revisadas: crea producto almacenable exclusivo de fábrica y categorías Familia → Subfamilia; usa los campos Tipo y Medida de ESI Calzados. La opción Componentes se decide por fila; las herramientas no se consideran consumibles automáticamente.
6. Bloquea códigos duplicados, coincidencias con productos existentes, unidades no seleccionadas y filas sin revisar. No sobrescribe registros existentes. Una segunda ejecución de filas importadas no vuelve a crearlas.
7. Conserva vínculo al producto creado y bloquea cambios de las filas ya importadas. Serializa ejecuciones concurrentes de este importador.

No importa costos todavía: el costo de catálogo es una referencia y no sustituye el costo de apertura del Kardex. Crear productos no carga stock ni valoración. El usuario debe validar que la unidad seleccionada representa la unidad del saldo, sin inventar conversiones de conos, rollos, latas o botes.

## Instalación y uso

1. Probar en una copia de la base de producción con respaldo. Este paquete no se ha instalado en un servidor Odoo durante su elaboración.
2. Requiere los módulos ESI existentes, en especial `esi_calzados_v20` 20.0.11.2.0 o posterior con `esi_material_type`, `esi_measure`, `esi_component_ok` y `esi_manufacture_ok`. Este ZIP contiene únicamente el nuevo módulo; no reemplaza ESI Calzados ni Sucursales.
3. Copiar `migrar_tosscano_v20` al directorio de addons, reiniciar Odoo, actualizar lista de aplicaciones e instalar «Migración Tosscano v20».
4. Activar matriz y las tres sucursales en el selector de compañías. Crear un registro de migración, seleccionar compañías y sus almacenes, guardar y pulsar «Preparar datos de origen».
5. Abrir «Revisar datos». Se muestran materias primas inicialmente; quitar ese filtro para revisar cuentas, saldos y recetas. Abrir una materia prima, revisar descripción/código/categorías, elegir unidad de inventario y marcar «Datos y unidad revisados». Importar únicamente filas revisadas.
6. Las categorías se buscan por nombre y padre exactos. Si ya existen categorías equivalentes con otro nombre, corregir Familia/Subfamilia antes de importar. La configuración contable de las categorías debe revisarse antes de valorar existencias.

## Pendientes concretos

- La copia disponible de `lista productos terminado.xlsx` tiene exactamente el mismo SHA-256 que `FICHAS DE COSTO MILITAR APROBADO.xlsx`: `a065ce6332f30898c0d3d1fe04d56bd59dce7c3fe535846f8b4f4226b03021f4`. Ambos son el libro de recetas. Se reconoce que el primer nombre debe corresponder al catálogo, pero hay que recibir nuevamente sus bytes correctos. No se deduce un catálogo definitivo de las hojas de stock.
- HIL-EST-20-CAF permanece en dos filas del origen: se bloquea su importación hasta definir si consolidar. No inventar códigos para superar el bloqueo.
- Las correcciones de la foto no autorizan a fusionar saldos de códigos reutilizados. Las referencias ambiguas quedan intactas en la evidencia del Kardex para resolver su correspondencia.
- Recetas: seis códigos ausentes, dos líneas sin código, conversiones de 16 códigos, bolsa/numeración con un mismo código y componentes talla 40. Las recetas se conservan completas en revisión; no se crean LdM incompletas ni consumos de talla 40 para todas las tallas.
- Las etapas/costos de mano de obra de las fichas no son duraciones por centro. No se inventan tiempos de fabricación.
- Plan contable: requiere revisión de las 26 observaciones anteriores y comparación con cuentas existentes; todavía no hay botón para crear cuentas.
- Inventario: se ha elegido RESUMEN/Kardex para materiales. Los saldos terminados provienen de sus tres hojas de inventario y necesitan confirmación de correspondencia/costo. Todavía no hay botón para aplicar ajustes. El corte 23/10/2026 es fecha de referencia, no una afirmación de retrodatación de movimientos o asientos.
- Productos terminados, recetas, cuentas y saldos están en preparación, no importados. No se envió ningún cambio al servidor de producción.

## Validación

Nueve pruebas locales de integridad de datos superadas: claves únicas, cantidades, correcciones por fila, evidencia, duplicado conservado, Kardex seleccionado y recetas conservadas. Python/XML/manifiesto/ACL comprobados estáticamente. Incluye tres pruebas de integración Odoo (carga repetida, producto exclusivo sin stock, rechazo de fila sin revisar); están pendientes de ejecución en Odoo 20. No se afirma validación de instalación ni de comportamiento completo en servidor.
