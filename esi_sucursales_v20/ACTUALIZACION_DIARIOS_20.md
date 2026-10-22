## 20.0.3.3.2

Se conserva la corrección de creación en Lista dentro de Sucursales. La herencia de la lista se aplica con prioridad 90 para ejecutarse después de las vistas habituales. Se conservan los permisos y el aislamiento por compañía de 20.0.3.3.1.

# Actualización ESI Sucursales Odoo 20 — 20.0.3.3.1

## Corrección adicional en 20.0.3.3.1 (Community)

En Odoo 20, la vista Kanban base `account.account_journal_view_kanban` contiene
`on_create="account_accountant.action_journal_create_wizard"`. Este asistente no
está disponible en instalaciones Community sin el addon Enterprise
`account_accountant` y el botón **Nuevo** produce la alerta «Falta una acción».

Se hereda la vista Kanban y se elimina `on_create`; también se establece
`quick_create="false"` para que la creación abra el formulario estándar
`account.journal`, que sí forma parte del addon `account` de Odoo 20 Community.
La corrección funciona tanto al mostrar los diarios en lista como en Kanban.
No se cambia el aislamiento por compañía ni se crean acciones ficticias.

## Problema detectado

Odoo 20 oculta el botón Nuevo de la lista de diarios mediante `js_class="list_no_create"`
(en la vista nativa `account.view_account_journal_tree`). El control de la compañía
`ir.access` presente en ESI restringe qué diarios ve y modifica el usuario, pero
no le da derechos de creación si no tiene un rol contable que lo permita.

## Cambios

1. `views/journal.xml`: restaura el botón Nuevo de la lista de diarios; la clase
   `list_no_create` se elimina de la vista heredada y queda `create=1`. Se conserva
   el formulario estándar de Odoo para crear el diario.
2. `security/ir.access.csv`: concede creación, lectura y modificación de diarios
   a administradores de Ajustes (`base.group_system`) y al grupo específico ESI.
   Los administradores contables nativos conservan sus permisos originales.
3. `security/groups.xml`: crea el grupo optativo **ESI - Diarios contables / Crear y editar diarios**
   para delegar esta operación a usuarios concretos. Los usuarios asignados
   deberán contar además con los permisos contables necesarios para configurar
   cuentas y medios de pago.
4. Mantiene `security/branches.xml`: los diarios están sujetos a
   `[('company_id', 'in', company_ids)]`. La configuración matriz y sucursal
   se gestionan individualmente, sin compartir todos los diarios automáticamente.
5. `views/journal.xml`: conserva la compañía editable al crear un diario, pero no
   permite cambiar su compañía una vez guardado.
6. Pruebas adicionales de lista, creación en matriz/sucursales, y prohibición
   de crear en una sucursal no autorizada.

## Instalación

Respaldar la base de datos. Reemplazar el directorio del addon
`esi_sucursales_v20` existente por el incluido (sin dejar copias con el mismo
nombre en el addons_path). Actualizar aplicaciones y pulsar **Actualizar**
en el módulo ESI Sucursales, o actualizar por línea de comandos.

Ejemplo para una instalación Docker del usuario que tenga contenedor `odoo20_01`:

```
docker exec -u odoo odoo20_01 /entrypoint.sh odoo -c /etc/odoo/odoo.conf \
  -d ESIBOLIVIA0001 -u esi_sucursales_v20 --stop-after-init --no-http
```

**NOTA:** Adaptar el nombre de base al entorno correcto. Si el contenedor ejecuta
Odoo permanentemente, conviene detener su proceso de aplicación antes de usar
un proceso de actualización separado para evitar concurrencia. También puede
actualizarse desde Apps sin usar el comando.

## Revisión posterior

- En Configuración → Usuarios, comprobar que el usuario tenga la compañía matriz
  y la sucursal en su lista de compañías permitidas.
- Seleccionar solo la compañía matriz; en Facturación → Configuración → Diarios
  debe aparecer Nuevo y se debe poder crear un diario (ej. `Prueba Matriz`).
- Seleccionar solo la sucursal y repetir la prueba (`Prueba Sucursal`).
- Si un usuario no es administrador de Ajustes o Contabilidad, asignarle el
  nuevo grupo ESI para gestionar diarios. Para configurar diarios bancarios
  también necesita permisos contables relacionados.
- Si la base tiene una regla llamada `Diarios exclusivos ... (copia)`, revisarla
  manualmente: fue creada como copia y no se elimina automáticamente. Si sus
  operaciones/dominio son diferentes de las de ESI, podría seguir bloqueando.
- Si la pestaña del navegador conserva caché, actualizar con Ctrl+F5.

## Límites

Estas pruebas unitarias se incluyen para ejecutarse en una base Odoo 20 con
PostgreSQL; no se han ejecutado dentro de un servidor Odoo en este entorno.

## Prueba de regresión añadida (20.0.3.3.1)

- Verificación del Kanban heredado: sin acción Enterprise y sin creación rápida.
- Verificación de la compañía predeterminada en nueva ficha de diario tanto en matriz como en sucursales.

## Si el problema sigue tras actualizar

1. Abrir Odoo en incógnito o forzar Ctrl+Shift+R.
2. En modo desarrollador entrar en Ajustes > Técnico > Vistas y revisar
   `account.account_journal_view_kanban` y sus vistas heredadas; la arquitectura
   resultante no debe incluir `on_create="account_accountant.action_journal_create_wizard"`.
3. Verificar que el módulo `esi_sucursales_v20` haya sido **actualizado**, no solo
   que se haya reiniciado el contenedor, y que el código nuevo esté en el addons_path.
4. Revisar otras vistas heredadas de Kanban instaladas después de esta actualización.
