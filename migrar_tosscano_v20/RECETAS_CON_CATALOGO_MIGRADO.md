# Recetas con productos y componentes migrados — 20.0.6.3.0

Actualizar migrar_tosscano_v20, reiniciar Odoo y actualizar el módulo en Aplicaciones. No repetir productos ni saldos.

1. En el registro existente pulse 3. Crear recetas de Fábrica. Se abren las doce fichas de origen.
2. Abra una ficha. Los productos terminados se proponen por código de modelo del catálogo migrado. Revise que la receta corresponda a su color/material y talla. Los modelos M-BT-03, M-L-00 y M-P-02 no tienen plantilla propia en el catálogo de inventario recibido: seleccione el producto existente correcto o complete primero ese catálogo.
3. Las coincidencias inequívocas de código se rellenan con el componente migrado. Una conversión nativa entre unidades relacionadas se calcula automáticamente. Si no existe relación entre latas/litros, conos/gramos o rollos/metros, la cantidad en unidad de inventario queda en cero: indique la cantidad real equivalente por par. No se asume que una lata es un litro ni un cono un gramo.
4. Para código ausente o ambiguo elija el material del catálogo ya migrado. El código ACC-BOL-CEL-35 de la ficha se reutilizó para bolsa y numeración; las dos líneas requieren confirmar su material. No se crean productos auxiliares para suplirlos.
5. Revise el tiempo por centro (inicialmente 1 minuto por par, provisional y no medido), marque Correspondencias y aplicación revisadas y pulse Crear receta con tallas y centros.

La receta nativa usa cantidades en la unidad de inventario del componente, todas las variantes de la plantilla, y los centros Corte, Aparado, Conformado, Solado y Terminado en Fábrica. No cambia costos, stock, valoración ni unidades de productos existentes. No crea una receta parcial si falta un material o una equivalencia.

Antes de preparar las fichas se archivan las recetas auxiliares de prueba creadas por la versión anterior que no tengan OF vinculadas. Sus productos se archivan solo sin movimientos ni existencias. No se eliminan los materiales auxiliares, pues otros documentos pueden referenciarlos. Los registros con OF se conservan y se informa el motivo. No se borran movimientos ni se renombran productos ajenos.

Se evita duplicar recetas identificadas por la migración y no se sobrescriben sus componentes en la repetición. Una receta manual del mismo producto/código en Fábrica se conserva. Los productos auxiliares ya no son seleccionables en las correspondencias.

Esta revisión corrige el uso del catálogo real y facilita completar las equivalencias faltantes; no afirma que las doce recetas ya estén creadas o listas para consumir inventario sin esas confirmaciones.

Validación: 69 pruebas locales de datos y métodos aislados, Python/XML y estructura del ZIP. Falta validación en Odoo real.
