# Precios de venta y tarifas — 20.0.7.0.0

Fuente: PRECIOS PRODUCTO TERMINADO.xlsx, Hoja1, columnas C (modelo), D (minorista), E (mayorista). Se conservan las 77 filas y su número de origen en data/sale_prices.json. Importes en BOB por par.

## Uso

En una base nueva, **1. Importar datos** incluye precios y listas. En una base ya importada con corte 28/10, actualizar el módulo, reiniciar Odoo y pulsar **4. Cargar precios de venta y tarifas**. No repetir saldos. Se requieren permisos de Ajustes y administración de Ventas.

Se crean dos listas nativas, Minorista y Mayorista, compartidas entre sucursales, con el nombre de la matriz. Se habilita la función de listas de precios para usuarios internos. La tarifa se selecciona en el cliente o la cotización. No se reasignan clientes, ventas existentes ni configuraciones del POS. Para POS, incorporar la lista a las listas disponibles de su configuración.

El precio minorista se coloca en Precio de venta de la plantilla y en una regla fija de la lista Minorista. Mayorista recibe su importe de la columna E; cuando está vacía, recibe el minorista, sin inventar descuento. Las reglas son por plantilla y abarcan todas sus tallas, incluidas las futuras. No se exige un volumen mínimo porque el archivo no lo especifica. No se crean escalas por cantidad.

No se modifican impuestos: la interpretación fiscal de los importes depende de los impuestos configurados en el producto. La columna F (Costo de producción) se conserva como referencia y no se aplica a standard_price, AVCO o valoración.

La correspondencia usa el código de modelo completo como prefijo delimitado, dando prioridad al más específico. No se aproximan códigos. Se conservan colores, tallas y plantillas existentes. Solo se asignan precios a productos vinculados a esta migración.

La repetición utiliza identificadores y marcadores por revisión: no duplica listas/reglas ni sobrescribe modificaciones manuales posteriores a la primera carga. Actualizar el ZIP no ejecuta la carga por sí solo. Para corregir una tarifa después de importarla, editar su regla en la lista de precios; el precio general de la plantilla es un campo separado.

## Cobertura e incidencias

65 de las 66 plantillas importadas tienen correspondencia. **EL-V-02-06** queda sin actualización: el archivo dice **E-V-02** y hace falta confirmar si son el mismo modelo. No se crea un producto nuevo para ocultar esta diferencia.

Se conservan los importes recibidos, aunque el mayorista supere al minorista:

| Modelo | Minorista | Mayorista |
|---|---:|---:|
| M-L-00 | 330 | 340 |
| M-L-01 | 330 | 340 |
| M-L-02 | 330 | 340 |

M-L-00 no tiene plantilla en el catálogo actual. Estas diferencias quedan también en el resultado de la importación.

El Excel incluye modelos que no están en el catálogo de inventario importado. Sus precios se conservan como evidencia; no se inventan descripciones, colores o productos para ellos:

C-CLK-02, C-CLS-01, C-CLS-02, C-GMN-01, C-PLY-02, E-V-02, E-V-03, E-V-04, E-V-05, E-V-07, E-V-08, E-V-09, E-V-11, E-V-13, E-V-14, E-V-17, E-V-18, E-V-19, E-V-20, E-V-21, ES-CL-00, ES-M-01, ES-M-02, ES-V-05, I-B-02, I-B-03, I-CH-02, I-CH-03, I-CL-04, I-CL-05, I-CL-07A, I-CL-07B, M-BT-03, M-L-00, M-P-02, M-P-03, M-PC-02, M-TCT-01, TK-CL-01, TK-CL-02, TK-CL-03B, TK-CL-04, TK-CL-05.

## Precios aplicables por plantilla

| Código importado | Modelo fuente | Minorista | Mayorista aplicado | Observación |
|---|---|---:|---:|---|
| M-L-01-05-00 | M-L-01 | 330 | 340 |  |
| M-L-01-02-00 | M-L-01 | 330 | 340 |  |
| M-L-01-02-01 | M-L-01 | 330 | 340 |  |
| M-L-02-02-00 | M-L-02 | 330 | 340 |  |
| M-L-01-03-01 | M-L-01 | 330 | 340 |  |
| M-L-01-03-00 | M-L-01 | 330 | 340 |  |
| M-L-01-01-00 | M-L-01 | 330 | 340 |  |
| M-L-02-01-00 | M-L-02 | 330 | 340 |  |
| M-L-01-04-00 | M-L-01 | 330 | 340 |  |
| M-L-01-02-00-PILOTO | M-L-01 | 330 | 340 |  |
| M-L-01-03-00-PILOTO | M-L-01 | 330 | 340 |  |
| M-L-03-03 | M-L-03 | 380 | 270 |  |
| M-TAR-02-04 | M-TAR-02 | 490 | 340 |  |
| M-RG-01-03 | M-RG-01 | 490 | 340 |  |
| M-RG-01-01 | M-RG-01 | 490 | 340 |  |
| M-TDP-01-03 | M-TDP-01 | 490 | 340 |  |
| M-TDP-01-08 | M-TDP-01 | 490 | 340 |  |
| M-TAR-01-02 | M-TAR-01 | 490 | 340 |  |
| M-TCS-01-01 | M-TCS-01 | 490 | 340 |  |
| M-W-01-09 | M-W-01 | 330 | 240 |  |
| M-W-01-10 | M-W-01 | 330 | 240 |  |
| M-PC-01-03 | M-PC-01 | 350 | 260 |  |
| M-PC-01-01 | M-PC-01 | 350 | 260 |  |
| M-P-01-03 | M-P-01 | 490 | 340 |  |
| M-P-01-08 | M-P-01 | 490 | 340 |  |
| M-P-01-02 | M-P-01 | 490 | 340 |  |
| M-P-01-01 | M-P-01 | 490 | 340 |  |
| M-BT-02-09 | M-BT-02 | 350 | 260 |  |
| M-BT-01-09 | M-BT-01 | 350 | 260 |  |
| M-BT-01-10 | M-BT-01 | 350 | 260 |  |
| I-CL-01-06-0A | I-CL-01 | 350 | 250 |  |
| I-CL-01-06-0D | I-CL-01 | 350 | 250 |  |
| I-CT-01-07 | I-CT-01 | 350 | 250 |  |
| I-CL-01-01 | I-CL-01 | 350 | 250 |  |
| TK-CL-03A-012 | TK-CL-03A | 350 | 250 |  |
| I-B-01-06 | I-B-01 | 600 | 350 |  |
| M-RG-01-04 | M-RG-01 | 490 | 340 |  |
| M-RG-01-08 | M-RG-01 | 490 | 340 |  |
| M-TDP-01-04 | M-TDP-01 | 490 | 340 |  |
| ES-V-01-01 | ES-V-01 | 220 | 150 |  |
| ES-V-02-01 | ES-V-02 | 220 | 150 |  |
| ES-V-03-01 | ES-V-03 | 220 | 150 |  |
| ES-V-04-01 | ES-V-04 | 220 | 150 |  |
| ES-M-03-01 | ES-M-03 | 220 | 150 |  |
| EL-V-01-01 | EL-V-01 | 220 | 220 | Sin mayorista: usa minorista |
| EL-V-01-11 | EL-V-01 | 220 | 220 | Sin mayorista: usa minorista |
| EL-V-01-06 | EL-V-01 | 220 | 220 | Sin mayorista: usa minorista |
| C-PLY-01-11 | C-PLY-01 | 220 | 220 | Sin mayorista: usa minorista |
| C-PLY-01-12 | C-PLY-01 | 220 | 220 | Sin mayorista: usa minorista |
| C-PLY-01-08 | C-PLY-01 | 220 | 220 | Sin mayorista: usa minorista |
| C-CLK-01-01 | C-CLK-01 | 220 | 220 | Sin mayorista: usa minorista |
| M-BT-04-01 | M-BT-04 | 1200 | 800 |  |
| M-TAR-01-03 | M-TAR-01 | 490 | 340 |  |
| M-TAR-01-04 | M-TAR-01 | 490 | 340 |  |
| M-TDP-01-02 | M-TDP-01 | 490 | 340 |  |
| ES-V-04-01-01 | ES-V-04 | 220 | 150 |  |
| ES-V-03-01-01 | ES-V-03 | 220 | 150 |  |
| ES-M-04-01 | ES-M-04 | 220 | 150 |  |
| E-V-06-07 | E-V-06 | 220 | 220 | Sin mayorista: usa minorista |
| E-V-12-01 | E-V-12 | 220 | 220 | Sin mayorista: usa minorista |
| I-CL-08-06-0A | I-CL-08 | 350 | 250 |  |
| I-CL-03-06-0A | I-CL-03 | 350 | 250 |  |
| I-CL-02-06-0A | I-CL-02 | 350 | 250 |  |
| I-CL-06-06-0A | I-CL-06 | 350 | 250 |  |
| I-CH-01-06-0A | I-CH-01 | 450 | 350 |  |
