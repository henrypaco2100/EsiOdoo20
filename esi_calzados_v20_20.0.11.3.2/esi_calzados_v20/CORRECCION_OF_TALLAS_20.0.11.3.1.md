# Corrección 20.0.11.3.1

- Corrige el falso positivo "Esta OF contiene componentes u operaciones manuales" al confirmar una OF por tallas en borrador.
- Los componentes generados automáticamente por Odoo/ESI en una OF de varias tallas ya no se interpretan como edición manual.
- La falta de stock ("No disponible") no bloquea la planificación por tallas; Odoo gestionará disponibilidad/reserva al confirmar y procesar la fabricación.
- La protección contra sobrescritura de componentes/operaciones manuales se conserva para OF normales o flujos legacy fuera del modo directo por tallas.
