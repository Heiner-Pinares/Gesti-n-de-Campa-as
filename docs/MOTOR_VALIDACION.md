# Motor de validación

## Flujo

El portal y el comando `validar_campanas` utilizan el mismo servicio:

1. Registran una fila en `TBL_VALIDACION_EJECUCION_GC`.
2. Consultan las fuentes Oracle sin modificarlas.
3. Cargan las campañas efectivas desde `CFG_CAMPANAS_PORTABILIDAD` y las versiones creadas en `TBL_CAMPANA_VERSION_GC`.
4. Evalúan cada caso con cálculos `Decimal`.
5. Guardan resultados y evidencias en `TBL_VALIDACION_RESULTADO_GC`.
6. Actualizan las cantidades y el estado final de la ejecución.

La ejecución manual se procesa en un hilo del servidor web. La ejecución programada debe invocar el comando de administración desde un programador externo autorizado.

## Consulta de fuentes

La consulta está en `validaciones/oracle_repository.py`. Utiliza bind variables para fechas, motivos y servicios excluidos. No contiene reglas comerciales mediante `CASE WHEN` y no ejecuta DML sobre las fuentes.

La fecha de elegibilidad utilizada es `BASE_FINAL_CAMPANA_HIST.VALIDO_DESDE`. Cuando no está disponible, el caso queda `POR_REVISAR`.

`CFG_CAMPANAS_PORTABILIDAD.COD_PLAN` y `BASE_CF_BASICO_X.PROD_OFFER` no son el mismo identificador: el primero contiene códigos comerciales numéricos y el segundo nombres de producto. El motor conserva `PROD_OFFER` como evidencia, pero no los compara hasta que exista un mapeo oficial. La selección actual utiliza campaña, operación, rango de cargo y vigencia.

Los parámetros configurables están en `.env`:

```dotenv
VALIDATION_REASON_MAP_JSON={"21":"Migra Pre a Post","2001":"Alta","2002":"Portabilidad"}
VALIDATION_EXCLUDED_SPCODES=3674
VALIDATION_MAX_DAYS=31
VALIDATION_BATCH_SIZE=500
VALIDATION_TOLERANCE=0.01
```

La interpretación de 2001 y el servicio excluido 3674 deben mantenerse alineados con la definición vigente del negocio.

## Clasificaciones seguras

- `CORRECTO`: existe una sola regla aplicable y la diferencia está dentro de la tolerancia.
- `ERROR`: existe una diferencia comprobada o falta un descuento requerido.
- `POR_REVISAR`: faltan datos, la fecha no está disponible, existen varias campañas, varios descuentos, devoluciones o reglas ambiguas.
- `NO_APLICA`: está disponible para reglas futuras que confirmen explícitamente que no corresponde beneficio. El motor no lo asigna por ausencia de información.

Los porcentajes se almacenan como factor decimal. Por ejemplo, 50% se almacena como `0.50`. Los montos fijos se almacenan en soles.

## Ejecución por comando

```powershell
.\scripts\run_campaign_validation.ps1 -Desde 2026-10-24 -Hasta 2026-10-27 -Tipo PROGRAMADA
```

El script no crea una tarea programada. La frecuencia, el horario y la cuenta de servicio deben aprobarse antes de configurarlo en Control-M o Windows Task Scheduler.

## Limitaciones conocidas

- La fuente no confirma todavía la fecha real de venta. Se usa `VALIDO_DESDE` porque es el campo asociado por el historial suministrado.
- Los registros con más de un descuento no se suman como si fueran un único beneficio; quedan para revisión.
- La clasificación compara el cargo adelantado `CF_ADEL` con el descuento adelantado correspondiente. `CF_PRO` se conserva como evidencia y no bloquea esa validación, porque el histórico suministrado muestra prorrateo en los casos conformes. El componente prorrateado no se certifica por separado todavía.
- Las devoluciones `CF_DEV` quedan para revisión hasta confirmar su regla de facturación.
- Las campañas fuente sin porcentaje requieren una versión del portal con tipo `MONTO_FIJO` y valor explícito.
- No se calcula todavía el número de periodos consumidos del beneficio porque no se confirmó una fuente confiable para ese dato.
