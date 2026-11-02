# Preparación para servidor Windows

Esta guía no instala un servicio, no programa tareas y no ejecuta migraciones. Es una preparación para el ambiente autorizado.

## Requisitos

- Windows Server de 64 bits.
- Python 3.12 x64.
- Acceso DNS y de red a `scan-odscbio:1521`.
- Cuenta de servicio de Windows definida por Infraestructura.
- Acceso autorizado a Oracle para `USRFACDOC[USRVALCBIO]`.
- PowerShell.

El portal usa `python-oracledb` Thin. No requiere Oracle Instant Client mientras la prueba de compatibilidad sea satisfactoria.

## Instalación portable

Desde PowerShell, en la raíz del proyecto:

```powershell
.\scripts\setup_windows.ps1
.\scripts\check_portable.ps1
```

Estos comandos crean `.venv`, instalan versiones fijadas y ejecutan pruebas con SQLite en memoria. No conectan a Oracle.

## Archivos privados

1. Copiar `.env.example` como `.env` y ajustar únicamente valores autorizados.
2. Crear `secrets\oracle_password.txt` con la contraseña Oracle como única línea.
3. Restringir `.env`, `secrets` y `data\incoming` a la cuenta de servicio y administradores.
4. Copiar las fuentes a `data\incoming` o configurar rutas absolutas mediante variables de entorno.

No copiar el `.env`, secretos, sesiones o datos de 4DX.

## Diagnóstico Oracle

```powershell
.\scripts\check_oracle.ps1
```

El comando ejecuta solamente una consulta a `DUAL` y muestra servicio, usuario de sesión, esquema y usuario proxy. No crea objetos ni modifica datos.

Después de comprobar la conexión, genere el inventario de metadatos y permisos:

```powershell
.\scripts\inspect_oracle_metadata.ps1
```

El resultado queda en `reports\oracle_metadata.json`. Solo consulta vistas de diccionario accesibles y cuenta los registros de la configuración de campañas; no incluye contratos, líneas ni datos de clientes.

## Crear el esquema propio del portal

Las tablas autorizadas usan exclusivamente el patrón `TBL_<NOMBRE>_GC`. No se utilizan migraciones automáticas de Django.

Primero revise el plan, sin ejecutar DDL:

```powershell
.\scripts\preview_oracle_schema.ps1
```

El DDL revisable está en `sql\oracle\001_create_tables_gc.sql`. Para crear únicamente los objetos faltantes:

```powershell
.\scripts\apply_oracle_schema.ps1
```

El comando valida que el esquema actual sea el configurado en `ORACLE_SCHEMA`, no contiene operaciones destructivas y puede reanudarse si algunos objetos ya existen.

Después cree el primer administrador. La contraseña se solicita de forma oculta y se almacena con el hash seguro de Django:

```powershell
.\scripts\create_portal_admin.ps1
```

No ejecute `manage.py migrate`: el portal no utiliza tablas `AUTH_*`, `DJANGO_SESSION` ni migraciones automáticas.

### Compatibilidad de fechas con Oracle Thin

Si el esquema se creó con una versión inicial que usaba `TIMESTAMP WITH TIME ZONE` y aparece `DPY-3022`, actualice el código y ejecute una sola vez:

```powershell
.\scripts\repair_oracle_timestamps.ps1
```

La reparación solo afecta las columnas técnicas de fecha de `TBL_*_GC`. Preserva los usuarios existentes y se detiene si detecta datos funcionales que requieran una revisión manual.

## Arranque de verificación

```powershell
.\scripts\run_windows.ps1
```

Waitress escucha en `0.0.0.0:8000` por defecto. El puerto, host y cantidad de hilos se pueden cambiar con `WEB_PORT`, `WEB_HOST` y `WEB_THREADS`.

No se debe exponer directamente el puerto a Internet. La publicación final debe coordinarse con Infraestructura mediante el proxy inverso corporativo, HTTPS, firewall y nombre DNS aprobados.

## Persistencia y autenticación

La autenticación, las campañas versionadas, las ejecuciones, los resultados y la auditoría utilizan las cinco tablas propias `TBL_*_GC`. El portal no requiere tablas estándar de Django ni ejecuta migraciones.

Después de actualizar el código en un servidor ya instalado, vuelva a recopilar los archivos estáticos antes de reiniciar:

```powershell
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

## Motor de validación

La ejecución manual se inicia desde la sección **Validaciones**. También se puede invocar el mismo motor por PowerShell:

```powershell
.\scripts\run_campaign_validation.ps1 -Desde 2026-10-24 -Hasta 2026-10-27 -Tipo PROGRAMADA
```

El proceso solo consulta las tablas fuente y escribe en `TBL_VALIDACION_EJECUCION_GC`, `TBL_VALIDACION_RESULTADO_GC` y `TBL_AUDITORIA_CAMBIO_GC`.

## Servicio de Windows y automatización

No se ha registrado un servicio de Windows ni una tarea en Task Scheduler. Antes de hacerlo se debe confirmar:

- Cuenta de servicio.
- Carpeta definitiva.
- Puerto y proxy.
- Política de reinicio y logs.
- Frecuencia y horario de validación.
- Zona horaria `America/Lima`.
- Parámetros del periodo a procesar.
- Concurrencia y reintentos.
