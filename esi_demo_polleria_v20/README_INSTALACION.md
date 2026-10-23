# ESI — DEMO POLLERÍA A LA BRASA — ODOO 20

## Alcance
Crea 38 productos (pollos, gaseosas, acompañamientos, salsas, empaques e insumos), 4 categorías POS, 3 proveedores ficticios y fotografías ilustrativas generadas localmente. Precios de los cuatro pollos exactamente según solicitud. Demás precios/costos aproximados y editables.

**Seguridad:** el instalador no cambia la configuración de tu caja ni tus sesiones abiertas, no altera movimientos históricos, no asigna cuentas contables, no crea asientos, no inventa inventario, no crea compras ni ventas registradas.

## Instalación
1. Hacer copia de seguridad de la base de pruebas.
2. Extraer la carpeta `esi_demo_polleria_v20` en tu ruta de addons personalizados de Odoo 20.
3. Reiniciar el contenedor Odoo.
4. Aplicaciones → Actualizar lista de aplicaciones → buscar `ESI | Demo Pollería a la Brasa` → Instalar.
5. Verificar productos con referencia `DEMO-POL-` en Punto de Venta > Productos.
6. En Configuración de Restaurante, asegurarse de NO restringir las nuevas categorías `DEMO POLLERÍA` (o agregarlas a las permitidas).
7. Cerrar y volver a abrir la pantalla del punto de venta para recargar productos. Si la sesión continúa abierta, no hay que cerrar la caja contablemente solo para recargar la interfaz.
8. Si la caja trabaja en otra compañía, revisar compañía, impuestos y listas de precios del producto y su disponibilidad en el POS.

## Consumir en local o para llevar
El POS de restaurante ya ofrece mesas y venta directa. El catálogo es común para ambas modalidades. El empaque se puede cobrar aparte mediante el producto `Envase para llevar` de Bs 2 (estimado). Si el negocio incluye envase sin cargo, cambiar el precio a cero. Odoo ofrece opciones de comer aquí / para llevar según configuración del restaurante.

## Compras, inventario y contabilidad
Los insumos están disponibles para crear solicitudes/órdenes de compra manualmente. Las gaseosas son productos comprables y vendibles. **No se crea automáticamente una LdM/receta ni se descuenta materia prima al vender un pollo.** Para deducción automática por recetas es necesaria una segunda etapa con Manufactura/POS (o desarrollo específico). Contabilidad recibe movimientos cuando se configuran correctamente diarios, medios de pago, impuestos y cierre de sesión; instalar un catálogo no genera balances ficticios.

## Imágenes
Las imágenes incluidas son **ilustraciones originales de referencia con rótulos** y no fotografías de marcas o platos. Sustituibles en la ficha de producto, sin depender de conexiones de internet.

## Desinstalación
No se recomienda desinstalar si se registraron operaciones con los productos. Mantener una base de DEMOSTRACIÓN independiente.

## Corrección 20.0.1.0.1
Se corrigió la carga de imágenes para Odoo 20 mediante `odoo.tools.binary.BinaryBytes`. Soluciona el error `product.template.image_1920: use BinaryValue instead of bytes`.
Si una instalación anterior falló, sustituir completamente la carpeta del módulo por esta versión y volver a intentar la instalación. No es necesario eliminar registros del negocio.
