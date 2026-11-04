# ESI Distribución de Snacks — Odoo 20 Community

Módulo independiente para distribuidores pequeños. Depende solamente de `sale` y `stock`.

## Alcance
- Registra visitas a clientes, próxima visita, observaciones y estado.
- Genera cotizaciones reales de `sale.order` desde visitas, y permite imprimir su documento estándar (nota de venta) desde Ventas.
- Accesos a Pedidos, Clientes y Productos de Odoo.
- Asistente opcional de prueba con 8 snacks, 4 clientes y 4 visitas iniciales; no publica asientos, valida stock ni modifica categorías ajenas.
- Categoría propia de ejemplo con AVCO (`average`) cuando el campo existe.

## Limitaciones
- No planifica rutas GPS, no ofrece geolocalización ni uso offline.
- El registro de visita es manual; no se afirma que el usuario estuvo físicamente en la tienda.
- El pedido de Odoo NO genera por sí solo asiento ni rebaja stock: la entrega y la factura siguen el flujo estándar.
- El ZIP se verificó estáticamente. Instalación y operación real requieren prueba en un Odoo 20.
- En la demo se usa la compañía activa; configurar moneda BOB y diarios en Odoo antes de cobrar/facturar.

## Instalación
1. Extraer `esi_demo_distribucion_snacks_v20` en addons.
2. Reiniciar Odoo y actualizar lista de aplicaciones.
3. Instalar `ESI - Distribución de Snacks`.
4. Asegurar permisos de Ventas al usuario que lo use.
5. Entrar en `Distribución Snacks > Visitas a clientes`.
6. SOLO en base de pruebas, cargar ejemplos desde el menú de administrador.
