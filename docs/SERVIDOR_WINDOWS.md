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
