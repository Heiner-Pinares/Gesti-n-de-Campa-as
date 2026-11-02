# Portal de Control de Campañas y Descuentos — Móvil Masivo

Proyecto independiente para administrar campañas comerciales y validar descuentos de Móvil Masivo sobre Oracle ODSCBIO.

## Estado

- Fase 0: diagnóstico completado.
- Fase 1: esqueleto seguro, Windows, conexión Oracle preparada y portal inicial implementados.
- Fase 2: análisis local de CSV, XLSX y SQL legacy completado.

No se abrió una conexión Oracle, no se ejecutaron migraciones y no se realizó DDL ni DML.

Documentación principal:

- `docs/FASE_0_DIAGNOSTICO.md`
- `docs/FASE_1_IMPLEMENTACION_SEGURA.md`
- `docs/FASE_2_ANALISIS_FUENTES_Y_SQL.md`
- `docs/SERVIDOR_WINDOWS.md`

## Arquitectura propuesta

- Python 3.12 y Django 5.2 en un proyecto independiente.
- Django Templates, CSS y JavaScript vanilla.
- `python-oracledb` Thin, inicialmente sin pool.
- Oracle en modo lectura durante las primeras fases.
- Reutilización selectiva de patrones de 4DX, sin modificar ni copiar sus tablas, datos, secretos o migraciones.
- Pruebas portables con SQLite en memoria y fixtures anonimizados.

## Pendientes para Oracle

1. Secreto Oracle específico para este proyecto o gestor corporativo autorizado.
2. Confirmación de autorización para usar `USRFACDOC[USRVALCBIO]` desde el servidor Windows.
3. Ejecución del diagnóstico de solo lectura.
4. Inventario de metadatos y privilegios.
5. Aprobación explícita antes de cualquier modelo persistente, DDL o migración.

No se debe copiar automáticamente el secreto local de 4DX ni ejecutar migraciones contra su esquema.
