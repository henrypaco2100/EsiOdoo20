# ESI | Gestión Agrícola – Familia Agrocons (Odoo 20 Community)

Una sola aplicación instalable `esi_demo_agrocons_v20` que utiliza los módulos estándar de Compras, Inventario, Ventas y Contabilidad.

## Contenido
- 4 parcelas ficticias (500 ha); propiedades propias y alquiladas y referencias de alquiler.
- Dos campañas de verano 2025/26 y 2026/27; preparada para crear campañas de invierno.
- Planes por parcela, presupuesto y comparación con costos operativos; calendario y bitácora.
- Maquinaria, mantenimiento, consumo de combustible, proveedores y servicios.
- Cosecha, pesaje físico y comercial, lotes, transportes, informes de toneladas y costos.
- Productos agrícolas, solicitud de compra y cotización de venta en BORRADOR.
- Botones separados para registrar consumos de insumos y entradas de soya a inventario **solo al confirmarlos**.

## IMPORTANTE: seguridad y límites
**Solo instalar y cargar datos de prueba en una base de pruebas.** El módulo no cambia la moneda, plan de cuentas, diario, existencias ni método de valoración de otros productos al instalarse. La configuración AVCO debe verificarse en la compañía y categoría correspondiente. La creación de un producto con costo inicial no implica que ya se haya configurado correctamente AVCO.

La carga DEMO genera bitácora y cosechas históricas **informativas**, no existencias históricas reales. Esto evita inventar asientos contables. Para comprobar los botones de stock, use labores nuevas con productos disponibles y valide manualmente el proceso. No debe pulsar el botón de cosecha sobre registros históricos para simular entradas retroactivas sin revisar la fecha y la valoración.

Los reportes de costos de este módulo son **operativos**, no sustituyen estados financieros ni valoración contable. Los precios en Bs y rendimientos son ficticios. Si se utiliza otra moneda principal, los valores de muestra deben ajustarse. Los descuentos por humedad/impurezas son informativos y no se deducen automáticamente de stock físico. Los pagos y facturas se tramitan en Odoo estándar.

El costo unitario de soya estimado se calcula en la ficha agrícola, pero **no se capitaliza automáticamente** en la valoración contable del grano: requiere diseño y comprobación contable adicional específica para la empresa. Esta limitación evita duplicar costos operativos y asientos de stock.

## Instalación
1. Respaldar la base de prueba.
2. Copiar la carpeta `esi_demo_agrocons_v20/` (no el ZIP entero) en los addons de Odoo 20.
3. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar el módulo.
4. Entrar a `Gestión Agrícola ESI > Configuración > Cargar DEMO Agrocons`, marcar la confirmación y ejecutar **una vez**. Repetir la carga no debe duplicar los registros principales.
5. Verificar moneda, almacenes, unidades de medida, seguimiento de lotes y método AVCO antes de validar stock.

## Operaciones que generan movimientos reales
- `Bitácora de labores > Registrar bitácora` solo registra la operación agrícola.
- `Validar consumo en inventario` crea movimientos reales del almacén a una ubicación de producción, con permisos de gerente de stock y comprobaciones de existencia; **es irreversible operativamente sin una devolución**.
- `Cosechas > Ingresar grano al inventario` genera entrada desde producción a almacén, exige producto almacenable rastreado por lote, y bloquea duplicados. Su valoración contable debe revisarse antes de usar el botón.

## Compatibilidad
API de `ir.access.csv` de Odoo 20. Verificación estática incluida en `tests/test_package.py`. La validación total requiere instalación en una instancia ejecutable de la misma versión de Odoo 20 con las apps dependientes.


## Corrección 20.0.2.0.1
Se corrigió la carga demo: `with_company()` se aplica al recordset del asistente, y no al objeto `Environment`, en ambos asistentes. No cambia movimientos de inventario ni contabilidad.


## Corrección de asistente 20.0.2.0.2
- Evita el campo eliminado `company_type` en `res.partner`; no fuerza la clasificación jurídica de contactos ficticios.
- Utiliza `uom_id` en líneas de compra de Odoo 20.
- Selecciona el campo disponible para configurar AVCO en la categoría agrícola y detiene la carga si no puede establecerlo.
- No confirma inventarios ni facturas al pulsar Cargar DEMO.
