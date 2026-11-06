# Creación de 12 recetas de demostración con centros — 20.0.6.2.0

Actualizar migrar_tosscano_v20. Abrir el registro existente, con Fábrica elegida, y pulsar 3. Crear recetas DEMO con centros. No repetir saldos. Requiere Fabricación administrativa y ESI Calzados con recorrido por centros.

El resultado abre las 12 recetas. Cada una tiene un producto DEMO propio y todas las tallas 34–46 seleccionadas en Variantes permitidas. Las cantidades de ingredientes son las cantidades por par de la ficha recibida, sin multiplicar de nuevo por el lote. Cada receta tiene Corte → Aparado → Conformado → Solado → Terminado asignados en Fábrica.

Para que las fichas puedan probarse sin inventar equivalencias, se crean materiales DEMO separados en las unidades de la ficha. Por ejemplo, el hilo de receta en gramos no se convierte automáticamente al cono del inventario; bolsa y numeración con el mismo código fuente son materiales DEMO distintos. Los precios de materiales son los unitarios de las fichas. Los materiales DEMO no reciben existencias ni se vinculan al saldo del catálogo real. Para fabricar será necesario abastecerlos en una base de prueba o configurar el consumo autorizado por Odoo.

Los modelos presentes solo en las fichas también reciben su plantilla DEMO: ya no quedan bloqueados por no aparecer en el inventario. No se crean combinaciones de color o material no especificadas.

Los centros usan un tiempo PROVISIONAL de 1 minuto por par, necesario para probar planificación y recorrido. No procede de una medición de fábrica. Revisarlo antes de usar planificación o costo operativo. Mano de obra y gastos monetarios de las fichas no se transforman en minutos.

La repetición conserva las recetas DEMO ya creadas, sus componentes y su recorrido; sincroniza únicamente las variantes permitidas. No duplica los centros. No cambia recetas manuales, unidades ni existencias del catálogo real.

Esta carga resuelve la demostración. Para fabricar consumiendo el inventario real todavía se necesitan las equivalencias documentadas en INCIDENCIAS_RECETAS.md. No es una conversión de unidades de ese inventario.

68 pruebas locales aprobadas y validación Python/XML/ZIP. Pendiente instalar y confirmar una fabricación en Odoo real.
