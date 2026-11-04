# Avances parciales por centro

Actualizar esi_calzados_v20 a 20.0.11.3.6. Incluye los cambios de costos, columnas y PDF de la revisión anterior.

Abra una orden confirmada con recorrido por centros o el tablero Fabricación por centros. En Cortado, pulse Registrar avance e indique 80 de 100. Quedan 20 pendientes allí y el siguiente centro recibe 80. Puede avanzar esos 80 en tandas. No se permite avanzar más de lo recibido. Cada registro queda en el historial de la OF.

La etapa nativa se cierra al completar la cantidad total, aunque se pueden registrar tandas en el centro siguiente antes de ese cierre. Avanzar no registra existencias, consumo ni salida de producto terminado. La OF se termina por el flujo habitual después de completar el recorrido. Se registra cantidad total por centro, no distribución por talla.

Validado localmente; verificar operación y PDF en una base de prueba Odoo.
