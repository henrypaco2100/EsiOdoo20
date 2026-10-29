# Migración Tosscano v20 - 20.0.7.1.0

Cambios para base nueva:

- Las tallas se crean y presentan siempre en orden numérico ascendente (34, 35, 36, 37, ...).
- Cada valor del atributo `Talla` recibe una secuencia numérica estable, evitando el orden mezclado por ID/creación.
- Los productos terminados se crean con `product_add_mode = matrix`.
- El migrador exige que `sale_product_matrix` esté disponible a través de `esi_calzados_v20`.
- Se mantiene la corrección de recetas/LdM de la versión 20.0.7.0.0.
