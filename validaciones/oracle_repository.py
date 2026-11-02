"""Consultas de solo lectura para el motor de validación."""

from datetime import datetime, time, timedelta

from django.db import connection


VALIDATION_SOURCE_SQL = """
WITH DESCUENTOS AS (
    SELECT
        CO_ID,
        INVOICING_DATE,
        SUM(NVL(CF_ADEL, 0)) AS DESCUENTO_APLICADO,
        COUNT(*) AS CANTIDAD_DESCUENTOS,
        MIN(SNCODE) AS SNCODE_DESCUENTO,
        MIN(SPCODE) AS SPCODE_DESCUENTO
    FROM USRVALCBIO.BASE_CF_DESCUENTO_X
    {discount_filter}
    GROUP BY CO_ID, INVOICING_DATE
), CAMPANAS AS (
    SELECT
        CO_ID,
        EMISION,
        MIN(VALOR) AS NOMBRE_CAMPANA,
        MIN(VALIDO_DESDE) AS FECHA_ELEGIBILIDAD,
        COUNT(DISTINCT VALOR) AS CANTIDAD_CAMPANAS
    FROM USRVALCBIO.BASE_FINAL_CAMPANA_HIST
    GROUP BY CO_ID, EMISION
)
SELECT DISTINCT
    T.INVOICE_ID,
    T.INVOICING_DATE,
    T.BILLSQNO,
    T.BILLING_MODE,
    T.CUSTOMER_ID,
    T.CO_ID,
    USRVALCBIO.TFUN001_GET_DNNUM_FROM_COID(T.CO_ID, T.INVOICING_DATE) AS LINEA,
    T.PROD_OFFER,
    T.CF_ADEL AS PLAN_MONTO,
    T.CF_PRO AS PLAN_PRORRATEO,
    T.CF_DEV AS PLAN_DEVOLUCION,
    T.MONTO_CON_IGV,
    CH.CH_REASON,
    RA.RS_DESC AS MOTIVO_ALTA,
    CH.CH_VALIDFROM AS FECHA_ACTIVACION,
    P.NOMBRE_CAMPANA,
    P.FECHA_ELEGIBILIDAD,
    P.CANTIDAD_CAMPANAS,
    D.DESCUENTO_APLICADO,
    D.CANTIDAD_DESCUENTOS,
    D.SNCODE_DESCUENTO,
    D.SPCODE_DESCUENTO
FROM USRVALCBIO.BASE_CF_BASICO_X T
INNER JOIN ODSCLARO.CONTRACT_HISTORY CH
    ON T.CO_ID = CH.CO_ID
INNER JOIN ODSCLARO.REASONSTATUS_ALL RA
    ON CH.CH_REASON = RA.RS_ID
LEFT JOIN CAMPANAS P
    ON T.CO_ID = P.CO_ID AND T.INVOICING_DATE = P.EMISION
LEFT JOIN DESCUENTOS D
    ON T.CO_ID = D.CO_ID AND T.INVOICING_DATE = D.INVOICING_DATE
WHERE CH.CH_SEQNO = 2
  AND CH.CH_VALIDFROM >= :desde
  AND CH.CH_VALIDFROM < :hasta_exclusiva
  AND CH.CH_REASON IN ({reason_binds})
  AND T.CH_STATUS = 'a'
ORDER BY T.INVOICING_DATE, T.CO_ID, T.INVOICE_ID
"""


def _bind_list(prefix, values, parameters):
    names = []
    for index, value in enumerate(values):
        name = f"{prefix}_{index}"
        names.append(f":{name}")
        parameters[name] = value
    return ", ".join(names)


def build_validation_query(reason_codes, excluded_spcodes):
    if not reason_codes:
        raise ValueError("Debe configurarse al menos un motivo de alta para validar.")
    parameters = {}
    reason_binds = _bind_list("reason", reason_codes, parameters)
    if excluded_spcodes:
        spcode_binds = _bind_list("spcode", excluded_spcodes, parameters)
        discount_filter = f"WHERE SPCODE NOT IN ({spcode_binds})"
    else:
        discount_filter = ""
    sql = VALIDATION_SOURCE_SQL.format(
        discount_filter=discount_filter,
        reason_binds=reason_binds,
    )
    return sql, parameters


def iter_source_cases(start, end, reason_codes, excluded_spcodes, batch_size=500):
    sql, parameters = build_validation_query(reason_codes, excluded_spcodes)
    parameters.update(
        {
            "desde": datetime.combine(start, time.min),
            "hasta_exclusiva": datetime.combine(end + timedelta(days=1), time.min),
        }
    )
    with connection.cursor() as cursor:
        cursor.arraysize = batch_size
        cursor.execute(sql, parameters)
        columns = [item[0].lower() for item in cursor.description]
        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            for row in batch:
                yield dict(zip(columns, row))
