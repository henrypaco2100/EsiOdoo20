# Recetas militares - modo estricto de producción

Fuente autoritativa: `FICHAS DE COSTO MILITAR APROBADO(3).xlsx`.

Esta versión elimina las interpretaciones agregadas anteriormente:

- NO convierte `PLANTILLAS` a una línea distinta por cada talla.
- NO convierte `NUMERACION LENGUA` o `NUMERACION BOLSA` a códigos por talla.
- NO crea materiales faltantes automáticamente.
- NO convierte litros/gramos/metros a LATA/CONO/BOTE/ROLLO por equivalencia de costo.
- NO crea una LdM parcial.

Cada línea positiva de la ficha se intenta crear con exactamente:

1. Código del Excel.
2. Nombre del Excel.
3. UDM del Excel.
4. Cantidad/par del Excel.

Si código, nombre o UDM no coinciden con la materia prima migrada, la LdM queda pendiente y el log indica la diferencia.

La evidencia incorporada contiene 12 fichas, 290 filas con código y 288 líneas con cantidad positiva.


## 20.0.7.3.0 — producción estricta
- Las cantidades de la ficha se copian como **cantidad por par**, sin multiplicar por 1000 ni convertir por costo.
- Se exige precisión `Product Unit` de al menos 4 decimales; por ejemplo `0.0455` se conserva como `0.0455`.
- No se crean materiales faltantes y no se convierten LITRO↔LATA/BOTE, GRAMO↔CONO ni KG↔ROLLO.
- Si código, nombre o UDM no coordinan con la materia prima migrada, la LdM completa queda pendiente.
- Toda LdM creada incluye el recorrido: **CORTE → APARADO → CONFORMADO → SOLADO → TERMINADO**. Los centros deben existir previamente en FABRICA; el migrador no los crea ni los adivina.
- Los importes de mano de obra del Excel son costos; no se usan como minutos. El tiempo por centro queda con el valor por defecto de `esi_calzados_v20` hasta que se configure el tiempo real.
