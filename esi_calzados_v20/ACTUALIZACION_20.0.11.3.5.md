# Calzados MRP 20.0.11.3.5

Sustituir la carpeta del módulo, reiniciar Odoo y actualizar esi_calzados_v20.
La actualización no modifica costos almacenados, existencias, valoración o consumos históricos.

La tabla Componentes distingue cantidad prevista, cantidad reservada/registrada y pendiente de consumo. Familia/categoría, material, unidad, cantidad por par, costo unitario, costo por par e importe estimado utilizan los movimientos y el total de fabricación. Los costos son visibles para administradores de Fabricación.

El total excluye cancelaciones y suma importes redondeados en la moneda de la OF. Si una unidad de consumo no tiene una referencia común con la unidad del producto, no se estima el costo de esa línea: se muestra el diagnóstico y el total queda identificado como parcial. Para LONA CAMBA, confirmar la unidad en la ficha del producto y en la receta; si se almacena en rollos y se consume por metros, configurar la equivalencia real antes de usar esa estimación.

En Imprimir se añaden Fabricación · Tosscano, Traslado · Tosscano y Compra / Solicitud · Tosscano. Usan el logo de la compañía, folio, fecha, líneas y firmas. El formato de compra distingue orden, solicitud de presupuesto y solicitud interna; la solicitud interna añade espacios para el control administrativo.

58 pruebas locales y verificación de sintaxis Python/XML. Pendiente instalar y renderizar en el servidor Odoo.
