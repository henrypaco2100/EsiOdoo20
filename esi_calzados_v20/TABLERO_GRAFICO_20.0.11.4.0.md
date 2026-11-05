# Tablero gráfico de fabricación por centros — 20.0.11.4.0

Reemplazar la carpeta esi_calzados_v20, reiniciar Odoo y actualizar el módulo en Aplicaciones. Recargar el navegador con Ctrl+Shift+R para cargar los nuevos assets.

Acceso: Fabricación → Operaciones → Tablero de fabricación por centros, o desde Fabricación por centros → Tablero de producción.

Pantalla independiente con tarjetas de indicadores y gráficos de Chart.js mediante el ciclo de vida nativo de Odoo 20. No es la matriz HTML anterior, ni una hoja de cálculo agregada a la aplicación Tableros. No requiere módulos Enterprise de hojas de cálculo.

- Compañía: una de las compañías activas y autorizadas de la sesión.
- Unidad: una sola unidad en cada consulta; no se mezclan pares con otras medidas.
- Período: fechas inclusivas en la zona horaria del usuario. Agrupación día, semana (lunes), mes o año. Accesos Hoy y últimos 7/30/90 días.
- Avances: suma de cantidades que salieron de cada etapa durante el período. Puede contar el mismo par en varias etapas.
- Finalizados en último centro: cantidades que completaron el recorrido dentro del período; no equivalen a entradas de inventario ya validadas.
- OF con avances: cantidad de órdenes distintas con registros en el período.
- Pendientes actuales: saldo actual por centro de las OF abiertas, independiente de las fechas consultadas.
- Gráficos: evolución por área, barras de avances y distribución de pendientes.
- Gráficos Odoo: abre la vista gráfica nativa con sus opciones de barras/líneas/circular y la tabla dinámica sobre los mismos avances, compañía, período y unidad.
- Matriz: conserva el acceso a la consulta previa, con sus filtros propios.

Los datos empiezan con los registros de avance de esta función; no se inventa historial anterior. No se modifican inventario, costos, valoración ni otros módulos. El ZIP conserva los cambios anteriores del módulo.

Validación: 64 pruebas locales, sintaxis Python/JS/XML, referencias de acciones, orden de carga del manifiesto y existencia de assets. Pruebas de servidor aisladas con dobles ORM, incluidos permisos por compañía, separación de unidad y distinción entre avances, finalizados y pendientes. No se ejecutó instalación, navegador o renderización visual en una instancia real Odoo.
