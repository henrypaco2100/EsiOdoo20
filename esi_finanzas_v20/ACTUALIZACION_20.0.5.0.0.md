# ESI Finanzas 20.0.5.0.0

Las mejoras están integradas en el módulo existente `esi_finanzas_v20`, por instrucción expresa del usuario. No depende de esi_financieros_clasicos_v20 y no requiere otro módulo.

## Instalación

Reemplace la carpeta `esi_finanzas_v20` por la de este ZIP, reinicie Odoo y actualice **Informes financieros**. No desinstale Finanzas.

Si ya instaló el complemento anterior, esta actualización desactiva su vista de asistente y su menú duplicado, conservando las configuraciones guardadas. No necesita desinstalarlo para actualizar Finanzas. No vuelva a actualizar el complemento anterior después de esta versión.

## Configuración

Facturación / Contabilidad → Configuración → Ajustes → bloque **Reportes financieros** → **Configurar reportes financieros**.
También se ofrece un acceso directo Configuración → Reportes financieros. Ambos abren la misma configuración; no se añade otro menú Ajustes.

Acceso de edición: administrador de Contabilidad. Añada una cuenta o título del plan, seleccione Balance o Resultados, compañía, orden y título opcional. Las cuentas sin configuración mantienen el orden por código. La secuencia es entre cuentas hermanas; las hijas siguen bajo sus padres. La configuración de la matriz se hereda por sus sucursales; una específica de la sucursal prevalece solo cuando se consulta esa sucursal. En la consolidación de la matriz se usa su propia configuración, no la de una sucursal aleatoria.

## Consultas

Reportes → Reportes financieros → Balance general / Estado de resultados / Sumas y saldos. Asistente con fechas, compañía/sucursal, diarios, cuentas, nivel de detalle, inclusión de cuentas sin movimiento, asientos publicados/borradores, consulta y exportación PDF/Excel.

Formato estándar basado en los PDF recibidos: A4, CUENTA / TÍTULO / MONTO, jerarquía nativa, subtotales en negrita, dos decimales y páginas numeradas. Se respetan los signos contables, las depreciaciones negativas y los resultados no cerrados; no se copian los importes de los ejemplos.

La matriz incluye solo descendientes autorizadas. No se agregan monedas diferentes, no se usa sudo y no se realizan eliminaciones intercompañía. La jerarquía requiere padres correctamente configurados en el plan contable. No se modifican asientos, fechas, inventario ni valoración.

Validación local: 8 pruebas de jerarquía, signos, subtotales, niveles, ceros, orden y ciclos; sintaxis Python/XML y referencias de vistas contra los módulos recibidos. Instalación y renderizado QWeb no ejecutados en un servidor Odoo real.
