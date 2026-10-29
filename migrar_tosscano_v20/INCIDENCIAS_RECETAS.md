# Estado de LdM militares — 20.0.7.0.0

Fuente: 12 fichas militares aprobadas del archivo entregado por el usuario. La migración ya no bloquea todas las recetas por códigos de talla o por UDM heredadas.

## Resuelto en esta versión

1. **Componentes por talla**
   - `PLANTILLAS` → `ACC-PLA-<TALLA>`
   - `NUMERACION LENGUA` → `ACC-ETQ-LEN-MIL-<TALLA>`
   - `NUMERACION BOLSA` → `ACC-ETQ-BOL-MIL-<TALLA>`
   Cada línea se restringe con «Aplicar a variantes» a la Talla correspondiente. Si una talla explícita de la ficha no existe aún en el catálogo de materiales, se crea desde la LdM aprobada.

2. **Materiales que aparecen en la LdM y faltan en el catálogo**
   Se crean únicamente desde la ficha aprobada, sin sustituirlos por materiales parecidos. Entre los códigos detectados están `ACC-PLTX-SF-2`, `ACC-TEPL-08-CEL`, `CUE-HUN-HID-VER`, `HTO-NOR-COY`, `TEX-PK-0.8-EST`, `TEX-PLN-MCR-25`, `TEX-PNP-06` y `TEX-TUB-06-BL`. Las líneas sin código de M-RG-01 reciben un identificador técnico estable.

3. **UDM distintas entre ficha e inventario heredado**
   Primero se intenta la conversión nativa de Odoo. Para empaques sin capacidad declarada en la fuente, se usa equivalencia de costo de apertura para preservar el costo aprobado por par. Esto no afirma una equivalencia física de LATA/CONO/BOTE/PAQUETE/ROLLO; debe validarse antes de producción.

## Pendientes por falta de producto terminado objetivo

Las siguientes fichas no tienen ninguna plantilla de producto terminado cuyo código comience con el modelo en el catálogo de existencias incluido en esta migración, por lo que no existe un objetivo legítimo donde crear la LdM:

- `M-BT-03` — BOTIN CON CIERRE
- `M-L-00` — LONA SIN CUELLO
- `M-P-02` — PILOTO SPORT

No se inventan esos productos terminados. Cuando se incorporen al catálogo, el botón de recetas podrá crear sus LdM.

## Alcance actual

Los otros 9 modelos de ficha tienen 27 plantillas objetivo en los datos migrados. La creación es idempotente y nunca crea deliberadamente una LdM parcial.
