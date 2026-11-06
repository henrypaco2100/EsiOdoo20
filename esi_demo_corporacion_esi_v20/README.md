# ESI Demo Corporacion ESI - Odoo 20

Modulo de carga controlada para una base nueva/demo.

## Estructura creada

- Matriz: **CORPORACION ESI**
- Sucursales nativas Odoo 20:
  - **SUCURSAL CENTRAL** - almacen `CEN`
  - **SUCURSAL SCZ** - almacen `SCZ`
  - **SUCURSAL CBBA** - almacen `CBA`
- Plan contable compartido entre matriz y sucursales.
- Diarios propios por entidad.
- Tipos de venta por sucursal:
  - VENTAS INMEDIATA
  - VENTAS POR ENTREGAR
- Tipos de compra por sucursal:
  - COMPRAS INMEDIATA
  - COMPRAS EXTERIOR
- 20 productos compartidos: 15 insumos de soya, 3 productos cosechados y 2 de apoyo.
- Categorias con **AVCO** y **valoracion automatica/perpetua**.

## Saldos fuente

Los saldos se toman de los PDF entregados por el usuario (Balance General y Estado de Resultado de AGROBALSEM) y se cargan en SUCURSAL CENTRAL porque la fuente no contiene desglose por sucursal.

La fuente presenta:

- Activo: Bs 5.221.800
- Pasivo + Patrimonio: Bs 5.222.300
- Diferencia documental: Bs 500
- Resultado del ejercicio: Bs 620.700

Para no modificar cifras de la fuente, se crean dos cuentas tecnicas visibles:

- `399998` Diferencia documental Balance General por conciliar (Debe Bs 500)
- `399999` Contrapartida tecnica saldos Estado de Resultado (Debe Bs 620.700)

El informe ESI de resultados muestra las cuentas nominales de la fuente y resultado Bs 620.700. El Balance queda contablemente cuadrado sin alterar los importes fuente.

## Inventario

No se crean cantidades fisicas de apertura automaticamente. Esto evita duplicar el saldo contable de inventarios ya cargado desde el Balance General. Los almacenes y productos quedan listos para ejecutar compras/recepciones reales de demo; a partir de esos movimientos Odoo calcula AVCO y el Kardex.

## Instalacion

1. Copiar la carpeta `esi_demo_corporacion_esi_v20` a `EsiOdoo20`.
2. Actualizar lista de aplicaciones.
3. Instalar **ESI | Demo Corporacion ESI - Multisucursal Agro**.
4. Abrir **Demo Corporacion ESI > Crear / actualizar demo**.
5. Elegir fecha para los saldos, marcar confirmacion y ejecutar.

El cargador es idempotente: volver a ejecutarlo actualiza configuraciones y no duplica el asiento de saldos ni los documentos demo.

## Dependencias ESI

El modulo usa los modelos reales entregados en el paquete del usuario:

- `esi_sucursales_v20`
- `esi_tipo_ventas_v20`
- `esi_tipo_compras_v20`
- `esi_finanzas_v20`
- `esi_kardex_v20`
- `esi_ventas_report_v20`
- `esi_compras_report_v20`

No modifica `esi_finanzas_v20`.

## Compatibilidad Odoo 20 - revisión 20.0.1.0.1

- Seguridad migrada al formato nativo de Odoo 20: `security/ir.access.csv` usa `operation=crud`.
- Se eliminó el formato antiguo `perm_read/perm_write/perm_create/perm_unlink`, que ya no existe en `ir.access` de Odoo 20.
- Para mantener un plan contable único compartido por matriz y sucursales, Caja/Bancos del plan fuente se clasifican técnicamente como Activo Corriente. Odoo 20 impide que una cuenta de tipo `asset_cash` sea compartida entre varias compañías.
