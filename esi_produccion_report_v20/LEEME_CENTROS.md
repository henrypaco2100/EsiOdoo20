# Reportes de producción 20.0.11.1.0

Actualización del módulo existente esi_produccion_report_v20. Reemplazar su carpeta, reiniciar Odoo y actualizar el módulo. No es necesario actualizar el importador Tosscano ni cargar nuevamente datos.

En Fabricación → Reportes → Informes de producción:
1. Seleccionar la sucursal propietaria de las OF (por ejemplo FABRICA CALZADO).
2. Elegir «Órdenes por centro de trabajo actual» o el resumen habitual.
3. Seleccionar opcionalmente «Centro de trabajo actual», fechas y estado.
4. Consultar, PDF o Excel usan el mismo conjunto de datos.

La columna identifica workcenter_id, no el nombre de la operación. Prioridad: etapas en progreso, después listas para iniciar, después primera pendiente según secuencia. Si hay centros paralelos en progreso, muestra todos; el filtro coincide con cualquiera. La lista se ordena por centro al seleccionar el nuevo contenido. Órdenes terminadas/canceladas no tienen centro activo; las terminadas siguen visibles sin filtro de centro. Sin órdenes de trabajo: «Sin centro asignado». No se inventan etapas para recetas sin operaciones/recorrido.

El filtro consulta la situación actual, no reconstruye el centro histórico a la fecha del reporte. Las fechas siguen filtrando el inicio o fin de la OF. No altera planificación, inventario ni valoración. El filtro de centro no se ofrece para Destajos. Se mantiene la separación por sucursal y los permisos existentes; no se amplía la matriz a todas las sucursales.

Siete pruebas de selección/resumen de centros ejecutadas sin Odoo, más validación Python/XML. Instalación y exportación reales pendientes de prueba en Odoo 20.
