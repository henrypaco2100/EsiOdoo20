# Validación de la versión 20.0.7.0.0

Se ejecutaron **68 pruebas standalone del migrador** y **55 pruebas standalone de `esi_calzados_v20`**, todas aprobadas. También se compiló el Python modificado sin errores de sintaxis.

Cobertura específica de esta revisión:

- productos terminados nuevos con `product_add_mode = matrix`;
- corrección a Matrix de terminados ya migrados mediante «Activar Componentes, Fabricar y Matrix»;
- selector de receta compartida con todas las tallas de la primera fila válida marcadas por defecto cuando la selección es nueva;
- 12 fichas militares en la fuente normalizada;
- expansión por talla de PLANTILLAS, NUMERACION LENGUA y NUMERACION BOLSA mediante «Aplicar a variantes»;
- creación controlada de componentes faltantes que sí figuran en la LdM aprobada;
- rechazo de LdM parcial cuando una línea no puede resolverse;
- idempotencia: una LdM ya vinculada no se duplica y una LdM manual existente no se modifica;
- reconocimiento de los tres modelos de ficha sin producto terminado objetivo actual: M-BT-03, M-L-00 y M-P-02.

La fuente de recetas conserva las 12 fichas aprobadas. Los 9 modelos con producto terminado alcanzan 27 plantillas en el catálogo actual.

## Advertencia de UDM heredadas

La fuente no proporciona capacidad física para algunos empaques heredados (por ejemplo LATA, CONO, BOTE, PAQUETE o ROLLO) mientras la ficha consume litros, gramos o metros. Cuando Odoo no dispone de conversión nativa, la migración calcula una fracción del producto inventariado que conserva el **costo aprobado por par**. Esto permite materializar la LdM sin inventar una capacidad física, pero la cantidad física de esos empaques debe validarse con Tosscano antes de usar la receta en producción real.

Las pruebas locales no sustituyen una actualización real en una copia de la base Odoo 20. Se recomienda probar primero el botón de recetas y una OF de cada familia antes de producción.
