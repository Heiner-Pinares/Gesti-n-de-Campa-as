# Manual básico de usuario

## Inicio

La pantalla muestra las campañas activas y el estado de la última ejecución. Las cantidades corresponden a esa ejecución, no a valores históricos fijos.

## Campañas

Los usuarios pueden buscar y filtrar campañas. Los administradores pueden crear campañas o abrir **Ver / editar**.

Al editar una campaña, el portal no reemplaza el registro histórico. Crea una versión nueva, desactiva la versión anterior del portal y registra el usuario, la fecha, el motivo y los valores anteriores y nuevos.

Para porcentajes, ingrese `50` si el descuento es 50%. Para montos fijos, ingrese el importe en soles.

Las campañas originales continúan en `CFG_CAMPANAS_PORTABILIDAD`. Las versiones administradas se guardan únicamente en las tablas propias `TBL_*_GC`.

## Validaciones

Un administrador selecciona las fechas y pulsa **Ejecutar validación**. La página puede cerrarse mientras el proceso continúa dentro del servidor web. El estado se actualiza automáticamente cada diez segundos.

Los resultados permiten filtrar por clasificación, operación y campaña. La búsqueda por contrato o línea y la exportación completa están reservadas al administrador. Los analistas ven esos identificadores enmascarados.

Cada fila tiene un detalle con la campaña, la regla, las fechas, los importes y el motivo de la clasificación.

## Interpretación

- **Correcto:** el descuento coincide con una regla identificada.
- **Error:** existe una diferencia comprobada.
- **Por revisar:** falta información o existe ambigüedad.
- **No aplica:** reservado para una regla explícita que determine que no corresponde descuento.

No cambie una campaña para forzar que un resultado aparezca correcto. Primero confirme la condición comercial y luego cree una versión con el motivo correspondiente.
