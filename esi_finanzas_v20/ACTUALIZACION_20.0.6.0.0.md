# ESI Finanzas 20.0.6.0.0 — opciones recuperadas de Odoo 13

## Actualización

Este ZIP contiene el mismo módulo `esi_finanzas_v20`. Reemplace su carpeta, reinicie Odoo y actualice **Informes financieros**. No desinstale Finanzas ni repita migraciones de cuentas/saldos.

Si instaló `esi_financieros_clasicos_v20`, su código antiguo puede prevalecer por el orden de carga. Actualice primero Finanzas para que los modelos/campos de configuración queden registrados en este módulo; después retire/desinstale aquel complemento antes de utilizar los nuevos reportes. Conserve una copia de sus configuraciones antes de retirarlo. La actualización desactiva también sus vistas y menú anteriores. No basta con borrar su carpeta mientras sigue instalado. Si nunca lo instaló, ignore este punto.

La indicación de 20.0.5.0.0 de mantener instalado ese complemento queda sustituida por esta instrucción.

## Configuración

Configuración → Ajustes → **Reportes financieros** → Configurar reportes financieros. Acceso directo: Configuración → Reportes financieros → Estructuras de Balance y Resultados.

Pulse **Crear estructuras estándar** (usuario administrador de Contabilidad) en la compañía correspondiente. Crea Balance y Resultados una sola vez; no sobrescribe una estructura estándar existente. Puede crear otras estructuras para distintos informes de la misma compañía y elegirlas en el asistente.

Cada título admite padre/hijos, código, secuencia, signo y estilo; valores obtenidos de cuentas explícitas, tipos contables, suma de hijos, referencia a otro título o fórmula con operaciones de suma/resta. Se permite incluir subcuentas, detalle plano/jerárquico/ninguno y excluir diarios por título. Los títulos invisibles siguen disponibles para las fórmulas. Los ciclos generan un mensaje de validación en lugar de una recursión indefinida.

El orden simple por cuentas de la versión anterior se conserva en otro acceso dentro del mismo menú. Se aplica cuando no se selecciona una estructura. Las estructuras avanzadas usan su propio orden y estilos.

## Asistentes

Balance, Resultados, Sumas y saldos, Libro mayor y Flujo de efectivo comparten consulta, PDF y Excel, con sus opciones aplicables:

- Compañía/matriz, sucursal específica y selección de varias sucursales autorizadas. La matriz incluye descendientes; ninguna selección amplía los permisos del usuario.
- Moneda de presentación con conversión mediante la API nativa de Odoo por compañía y fecha; tasa de cierre del período o tasa de cada movimiento. No se multiplican todas las compañías por una tasa única. Una moneda extranjera sin tasa vigente bloquea el informe con un mensaje claro. No modifica las monedas de compañías ni los apuntes originales.
- Publicados o publicados más borradores; nunca asientos cancelados.
- Todas las cuentas, cuentas con movimiento/saldo inicial, o cuentas con saldo distinto de cero.
- Cuentas contables, diarios incluidos/excluidos, contactos, cuentas analíticas y clasificación de flujo.
- Débito/crédito opcional en Balance y Resultados. Comparación de fechas con etiqueta propia y variación; puede coexistir con débito/crédito. Se conservan títulos para cuentas con actividad solamente en el período comparado.
- Filtro analítico proporcional o asientos completos. Sumas y saldos y Mayor abren con asientos completos para conservar las contrapartidas dentro del ámbito de cuentas/diarios seleccionado. La selección proporcional admite varias cuentas del mismo plan analítico; para planes distintos se utiliza asientos completos, evitando duplicar importes entre planes.
- Desglose informativo por analítica o contacto en estados/sumas y saldos; no alimenta los subtotales nuevamente. En el Mayor puede mostrar columnas de analítica/contacto.
- Mayor con saldo inicial opcional, orden por fecha o diario/contacto, formato clásico/minimalista y moneda/importe de origen opcionales.
- Flujo de efectivo por actividad o por cuentas/categorías jerárquicas. Informa saldo inicial, entradas, salidas, cambio neto y saldo final. La clasificación en apuntes se mantiene separada de importes y fechas. Antes de publicar un asiento, una clasificación única en contrapartidas se copia únicamente a las líneas de liquidez vacías; si existen varias, no se adivina.

Los otros reportes existentes (vencimientos, estado de cuenta, analítico, ejecutivo, impuestos, caja/bancos) se mantienen; no se eliminan sus opciones. La conversión y el nuevo motor descritos aquí se aplican a los cinco reportes indicados, no se presenta como reimplementación de todos los informes del sistema.

## Formato y criterios

Formato estándar parecido a los PDF proporcionados: compañía y NIT, título, moneda, fechas, entidades y filtros; CUENTA / TÍTULO / MONTO con columnas opcionales; títulos/subtotales en negrita, estilos configurables, importes con dos decimales y páginas numeradas. PDF horizontal si se activan muchas columnas. Excel mantiene números, códigos como texto, encabezados, anchos y dos decimales.

Balance incluye los saldos hasta la fecha final. Resultados usa solo el período. La estructura estándar separa el resultado acumulado sin cierre del patrimonio registrado y muestra diferencia de cuadre; no elimina diferencias con ajustes inventados. La depreciación conserva su signo real.

Las fórmulas suman/restan el saldo presentado por los títulos referenciados. Invertir signo afecta los saldos; débito y crédito muestran movimientos reales. Un subtotal no se suma de nuevo por cada detalle impreso. Los filtros y desgloses parciales se indican en la cabecera. La conversión es una presentación de saldos: no genera asientos de diferencia cambiaria ni eliminaciones intercompañía y no sustituye un proceso de consolidación legal.

## Revisión de la versión 13

Se revisaron `bi_financial_pdf_reports` y `bi_financial_excel_reports`: definición de informes/líneas, asistentes de Balance/Resultados/Mayor/Sumas y saldos, métodos de cálculo, comparación, desgloses, flujo, exportación y plantillas. Se recuperan las funciones mediante código para Odoo 20; no se copian APIs obsoletas (`user_type_id`, `_query_get`/SQL heredado, `attrs`, `tree`, `post`). La relación con tipos contables se adapta a `account_type`; la analítica a distribución porcentual; el flujo a `_post`; las vistas a `list` y expresiones actuales.

Las personalizaciones y selecciones guardadas dentro de una base Odoo 13 no están contenidas en este archivo de código y no se inventan: deben exportarse de esa base si se requiere reproducirlas exactamente. Se entrega estructura estándar editable para comenzar.

## Verificación y límites

33 pruebas locales: jerarquía, signos, detalle, fórmulas, ciclos, diarios excluidos, tipos/cuentas, creación estándar idempotente, cuadre, analítica, flujo, conversión por compañía/fecha/cache, tasas faltantes, Excel numérico y seguridad de fórmulas, y escape HTML. Python/XML, referencias y anclajes de vistas revisados con el código nativo local de Odoo 20 y el paquete recibido.

No se dispone de un servidor Odoo/PostgreSQL para comprobar instalación y renderizado QWeb de extremo a extremo. No se declara probada la instalación ni el PDF real. Los informes limitan a 100.000 apuntes y piden reducir cuentas/diarios/ámbito cuando se supera; nunca entregan totales truncados. No se alteran inventario, valoración, cantidades ni fechas.
