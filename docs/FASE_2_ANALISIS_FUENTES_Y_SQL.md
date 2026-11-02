# Fase 2 — Análisis de fuentes y SQL legacy

Fecha: 02/11/2026

Los tres archivos se trataron exclusivamente como fuentes de datos. No se siguieron fórmulas, textos o instrucciones internas como órdenes de ejecución.

## 1. BASE_CF_BASICO.csv

### Estructura

- 18,963 filas.
- 46 columnas.
- UTF-8 con BOM y delimitador punto y coma.
- 0 filas completamente duplicadas.
- 36 filas sin campaña histórica (`VALOR`).
- 4,517 filas sin descuento asociado (`SNCODE.1`).

### Resultado legacy recalculado

| Clasificación | Filas |
|---|---:|
| Correctas | 11,639 |
| Error | 6 |
| Sin clasificación | 7,318 |
| Total | 18,963 |

Las 11,639 correctas tienen descuento asociado. De los seis errores, cuatro no tienen descuento y dos sí tienen un descuento distinto del monto esperado.

Las 7,318 filas sin clasificación se dividen en:

- 4,513 sin descuento asociado.
- 2,805 con descuento asociado.
- 4,097 con motivo de alta 2001.
- 2,241 con motivo 2002.
- 980 con motivo 21.

Campañas más frecuentes dentro de las no clasificadas:

| Campaña | Filas |
|---|---:|
| ALTA REGULAR | 3,233 |
| ATAQUE PLAN ILIMITADO | 711 |
| PORTABILIDAD EXCLUSIVA | 547 |
| PORTABILIDAD LINEA ADICIONAL | 513 |
| PROMOCION PORTABILIDAD PRESENCIAL | 273 |
| ALTA DTO UNIVERSITARIO | 210 |
| FULL CLARO ESPECIAL | 197 |
| PROMO TIENDA VIRTUAL | 182 |
| PROMOCION DAC VIRTUAL | 179 |

Esto demuestra que “sin clasificación” no equivale automáticamente a descuento incorrecto. La mayoría está fuera de las ramas del `CASE` legacy.

### Duplicados y claves

- `INVOICE_ID` no es una clave única: 806 filas pertenecen a 348 grupos repetidos.
- `CO_ID + INVOICING_DATE` tiene dos grupos repetidos, cuatro filas en total.
- Se necesita definir una clave de negocio que incluya al menos contrato, emisión, servicio/cargo y versión de la ejecución.

### Diferencias entre los campos de la base y CONTRACT_HISTORY

La consulta selecciona tanto `T.CH_*` como `CH.CH_*` sin aliases claros.

- `CH.CH_SEQNO` es 2 en las 18,963 filas, porque así se filtra.
- `T.CH_SEQNO` difiere en 462 filas: aparecen secuencias 4, 6 y 10.
- `T.CH_REASON` y `CH.CH_REASON` difieren en 462 filas.
- En esas filas también difiere `CH_VALIDFROM`.

El portal debe conservar ambos orígenes con nombres explícitos y establecer cuál es la fuente autorizada para elegibilidad.

## 2. CFG_CAMPANAS_PORTABILIDAD.csv

### Estructura

- 102 reglas.
- 16 columnas reales.
- 20 activas y 82 desactivadas.
- `TIPO_FILTRO`: 82 `F`, 17 `L` y 3 `S`.
- Entre las activas: 19 `F` y 1 `S`.
- Todas las reglas activas tienen vigencia inicial y final.
- Cuatro filas no tienen `COD_PLAN`.

`PORCENTAJE` se almacena como fracción: `0.3` y `0.5`. La interfaz lo presenta como 30% y 50%.

Hay tres reglas sin porcentaje. Corresponden a beneficios monetarios descritos como S/ 5 o S/ 10. Solo la ID 102 está activa:

- Campaña: PROMO MIGRA PRE A POST.
- Plan: S/ 29.90.
- Beneficio confirmado por el consolidado y la consulta: S/ 10.
- Duración: 12 meses.
- Vigencia: 16/10/2026–31/10/2026.

El valor fijo debe migrarse a un campo numérico explícito. No debe extraerse permanentemente de `DESCRIPCION`.

### Reglas activas relevantes que el SQL no cubre por completo

- PROMOCION PORTABILIDAD PRESENCIAL: incluye 49.90–60.90 por 6 meses, 69.90–79.90 por 6 meses y 95.90–289.90 por 12 meses.
- DTO PORTABILIDAD POSTPAGO y PORTABILIDAD TELEVENTAS: incluyen 56.90 por 6 meses y 60.90–289.90 por 12 meses.
- PORTABILIDAD PRESENCIAL CADENAS: 69.90–79.90 por 6 meses y 95.90–289.90 por 12 meses.
- PROMO MIGRA PRE A POST: S/ 10 para 29.90 y 30% para 39.90 y 49.90, por 12 meses.

El SQL agrupa las cuatro campañas de portabilidad con un único rango `>=69.90 AND <290`, por lo que pierde reglas específicas de planes inferiores y duraciones distintas.

### TIPO_FILTRO

La evidencia sugiere que `S` está relacionado con descuentos en soles y que las reglas activas `F` son porcentuales. Esto no confirma la semántica oficial. `L` solo aparece en reglas desactivadas del archivo analizado. Se mantiene como pendiente funcional.

## 3. Consolidado de Móvil Masivo

El libro tiene cuatro hojas:

| Hoja | Dimensión | Observación |
|---|---|---|
| Postpago Consumer | 99 × 45 | Matriz comercial con campañas, planes y beneficios |
| Hoja1 | 18 × 6 | Hoja oculta de apoyo |
| Campañas | 71 × 21 | Catálogo comercial; 62 fórmulas de estado |
| Actualizaciones | 28 × 5 | Historial narrativo de cambios |

La hoja `Campañas` incluye producto, segmento, operación, transacción, modalidad, código, nombres SISACT/BSCS, fechas, canales y zonas. No se identificó un campo PEO explícito.

Las fórmulas de estado usan `TODAY()`. El portal no debe importar el texto calculado como verdad histórica; debe evaluar vigencia con fechas tipadas y la fecha de elegibilidad autorizada.

Confirmaciones comerciales encontradas:

- PROMO MIGRA PRE A POST: S/ 10 × 12 meses para 29.90; 30% × 12 meses para 39.90 y 49.90.
- DTO PORTABILIDAD POSTPAGO y PORTABILIDAD TELEVENTAS: 50% × 6 meses para 56.90 y 50% × 12 meses desde 60.90.
- PROMOCION PORTABILIDAD PRESENCIAL: 50% × 6 meses para planes bajos y 50% × 12 meses desde 95.90.
- PORTABILIDAD PRESENCIAL CADENAS: 50% × 6 meses en 69.90/79.90 y 50% × 12 meses desde 95.90.
- PORTA ADICIONAL CON DTO: la matriz muestra S/ 29.90 × 12 meses para el plan 79.90.

Existe un conflicto que requiere confirmación: el SQL también acepta plan 95.90 para las campañas adicionales, pero la matriz revisada solo muestra el descuento económico en 79.90.

## 4. Problemas del SQL legacy

1. Las fechas son cadenas (`'24/10/2026'`) y dependen de `NLS_DATE_FORMAT`. Deben ser bind variables `DATE` o usar conversiones explícitas.
2. Los parámetros comerciales están hardcodeados en dos `CASE`.
3. Hay columnas repetidas de descuentos (`PROD_OFFER`, `SERV_LONG_DES`) y columnas duplicadas de contrato sin aliases.
4. El mensaje `ERROR TIENE DESCUENTO` se emite cuando `D.SNCODE IS NULL`; el texto contradice la condición.
5. Para portabilidad, un descuento incorrecto pero no nulo no recibe error: queda sin clasificación.
6. Para migración 39.90/49.90, un descuento incorrecto o ausente tampoco recibe una rama de error.
7. Las campañas adicionales solo comprueban existencia, no monto. El consolidado indica S/ 29.90 para un escenario concreto.
8. La selección de planes de portabilidad no coincide con las reglas activas del CSV/consolidado.
9. `BASE_FINAL_CAMPANA_HIST` no tiene propietario explícito en la consulta.
10. Los joins a campaña histórica y descuentos pueden multiplicar filas si existen varias coincidencias.
11. `SELECT *` dentro del subquery de descuentos dificulta controlar columnas y rendimiento.
12. `tfun001_get_dnnum_from_coid` exige validar privilegio, coste por fila y tratamiento de errores.
13. Se filtra `T.CH_STATUS='a'`, pero se selecciona también `CH.CH_STATUS`; debe aclararse el estado autorizado.
14. La comparación monetaria usa igualdad exacta y presupone descuento negativo.
15. No hay tratamiento completo de prorrateos, IGV, reversas, tolerancia ni meses consumidos.

## 5. Decisiones aplicadas al código

- El motor usa `Decimal`, no `float`.
- El signo del descuento se normaliza dentro de la capa de cálculo.
- Los valores se redondean a dos decimales con una política explícita y testeable.
- Una regla ausente o varias reglas coincidentes producen `POR_REVISAR`.
- Un descuento requerido ausente produce `ERROR` solo después de identificar una regla única.
- La fecha de elegibilidad es obligatoria; si falta, el resultado es `POR_REVISAR`.
- Los límites del motor inicial se implementaron inclusivos para probar el mecanismo. La política final debe confirmarse antes de cargar reglas productivas.

## 6. Pendientes antes de afirmar equivalencia

- Confirmar `TIPO_FILTRO` F/L/S.
- Confirmar motivo 2001.
- Confirmar fuente de fecha de venta.
- Confirmar plan 95.90 de líneas adicionales.
- Confirmar política de redondeo, tolerancia e IGV.
- Confirmar servicio(s) de descuento y reglas de agregación cuando hay varios.
- Consultar metadatos y privilegios reales en Oracle.
- Ejecutar comparación fila a fila con identificadores anonimizados.
