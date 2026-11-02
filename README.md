# Portal de Control de Campañas y Descuentos — Móvil Masivo

Proyecto independiente para administrar campañas comerciales y validar descuentos de Móvil Masivo sobre Oracle ODSCBIO.

## Estado

- Fase 0: diagnóstico completado.
- Fase 1: conexión y metadatos Oracle comprobados en el servidor Windows.
- Fase 2: análisis local de CSV, XLSX y SQL legacy completado.
- Fase 3: modelo persistente Oracle aprobado e implementado con nomenclatura `TBL_*_GC`.

El portal no ejecuta migraciones ni DDL al iniciar. La creación del esquema se realiza solamente mediante el comando explícito documentado para Windows.

Documentación principal:

- `docs/FASE_0_DIAGNOSTICO.md`
- `docs/FASE_1_IMPLEMENTACION_SEGURA.md`
- `docs/FASE_2_ANALISIS_FUENTES_Y_SQL.md`
- `docs/SERVIDOR_WINDOWS.md`

## Arquitectura propuesta

- Python 3.12 y Django 5.2 en un proyecto independiente.
- Django Templates, CSS y JavaScript vanilla.
- `python-oracledb` Thin, inicialmente sin pool.
- Oracle en lectura para las fuentes de facturación y con escritura limitada a las tablas propias `TBL_*_GC`.
- Autenticación propia en `TBL_USUARIO_GC` y sesiones firmadas, sin tablas estándar `AUTH_*`.
- Reutilización selectiva de patrones de 4DX, sin modificar ni copiar sus tablas, datos, secretos o migraciones.
- Pruebas portables con SQLite en memoria y fixtures anonimizados.

## Instalación resumida en Windows

1. Configure `.env` y `secrets\oracle_password.txt`.
2. Ejecute `scripts\setup_windows.ps1`.
3. Compruebe la conexión con `scripts\check_oracle.ps1`.
4. Revise `sql\oracle\001_create_tables_gc.sql` y `scripts\preview_oracle_schema.ps1`.
5. Cree los objetos autorizados con `scripts\apply_oracle_schema.ps1`.
6. Cree el administrador con `scripts\create_portal_admin.ps1`.
7. Inicie el portal mediante `scripts\run_windows.ps1`.

No se debe copiar el secreto de 4DX ni ejecutar `manage.py migrate`.
