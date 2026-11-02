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

## Arranque de verificación

```powershell
.\scripts\run_windows.ps1
```

Waitress escucha en `0.0.0.0:8000` por defecto. El puerto, host y cantidad de hilos se pueden cambiar con `WEB_PORT`, `WEB_HOST` y `WEB_THREADS`.

No se debe exponer directamente el puerto a Internet. La publicación final debe coordinarse con Infraestructura mediante el proxy inverso corporativo, HTTPS, firewall y nombre DNS aprobados.

## Persistencia y autenticación

El código incluye autenticación Django, pero sus tablas todavía no se han creado porque cualquier DDL requiere aprobación. Hasta aprobar el modelo y las migraciones, el arranque productivo no está habilitado como entrega final.

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
