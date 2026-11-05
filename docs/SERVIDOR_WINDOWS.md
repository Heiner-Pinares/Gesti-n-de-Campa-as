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

La cuenta que ejecuta Waitress necesita permisos de lectura y modificación sobre la carpeta configurada en `COMMERCIAL_XLSX_PATH`. Son necesarios para que un administrador pueda actualizar el Consolidado desde el portal y para crear el respaldo `.previous.xlsx`. No otorgue acceso a usuarios de Windows que no administren el proceso.

No copiar el `.env`, secretos, sesiones o datos de 4DX.

Para la primera prueba dentro de la red corporativa:

```dotenv
DEBUG=False
ALLOWED_HOSTS=*
HOST=0.0.0.0
PORT=8000
THREADS=8
```

`ALLOWED_HOSTS=*` es temporal. Cuando se confirme la dirección definitiva, reemplácelo, por ejemplo:

```dotenv
ALLOWED_HOSTS=172.19.194.219,LIMDOCFACTV02
```

No escriba esa IP en el código ni en `HOST`: Waitress debe continuar escuchando en `0.0.0.0`.

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

## Arranque en la red corporativa

```powershell
.\scripts\run_windows.ps1
```

El comando directo equivalente es:

```powershell
.\.venv\Scripts\python.exe run.py
```

`run.py` realiza, en este orden:

1. Carga `.env` y exige `DEBUG=False`.
2. Comprueba la conexión Oracle sin crear ni modificar datos.
3. Ejecuta `collectstatic --noinput`.
4. Detecta una IPv4 local solo para mostrar la URL.
5. Inicia Waitress en `0.0.0.0:8000` con ocho hilos por defecto.

No ejecuta migraciones ni DDL. La IP detectada nunca se utiliza como dirección de escucha.

La terminal mostrará:

```text
Portal iniciado.
Escuchando en: http://0.0.0.0:8000
Acceso local: http://127.0.0.1:8000
Acceso desde la red: http://IP_DEL_SERVIDOR:8000
Migraciones automáticas: deshabilitadas.
```

Compruebe la IPv4 vigente del servidor:

```powershell
ipconfig
```

Compruebe que el proceso escucha en todas las interfaces:

```powershell
netstat -ano | findstr :8000
```

La salida debe contener `0.0.0.0:8000` en estado `LISTENING`. Desde otra computadora de la misma red, abra `http://IP_DEL_SERVIDOR:8000`.

Las variables históricas `WEB_HOST`, `WEB_PORT` y `WEB_THREADS` siguen siendo compatibles, pero para nuevas instalaciones utilice `HOST`, `PORT` y `THREADS`.

No se debe exponer directamente el puerto a Internet. La publicación final debe coordinarse con Infraestructura mediante el proxy inverso corporativo, HTTPS, firewall y nombre DNS aprobados.

## Firewall de Windows

El proyecto no modifica el firewall automáticamente. Primero revise los perfiles activos y si ya existe una regla:

```powershell
Get-NetConnectionProfile
Get-NetFirewallRule -DisplayName "Portal interno - puerto 8000" -ErrorAction SilentlyContinue
```

Si otro equipo no puede acceder y no existe una regla autorizada, ejecute como Administrador únicamente para los perfiles Domain y Private:

```powershell
netsh advfirewall firewall add rule name="Portal interno - puerto 8000" dir=in action=allow protocol=TCP localport=8000 profile=domain,private
```

Para eliminarla:

```powershell
netsh advfirewall firewall delete rule name="Portal interno - puerto 8000"
```

No abra el perfil Public, no desactive el firewall y no configure port forwarding, ngrok ni exposición en el router.

Si funciona en el servidor pero no desde otro equipo, compruebe:

- Ambos equipos pertenecen a la red corporativa correspondiente.
- `netstat` muestra `0.0.0.0:8000` y no `127.0.0.1:8000`.
- `ALLOWED_HOSTS` admite la IP o el nombre usado.
- El Firewall de Windows permite TCP 8000 en Domain/Private.
- No hay una VPN o política de red que impida conexiones entre equipos.
- El puerto 8000 no está ocupado por otro proceso.

Escuchar en `0.0.0.0` publica únicamente el portal web. Oracle continúa como servicio externo en `scan-odscbio:1521`; no abra el puerto 1521 para los usuarios del portal.

## Persistencia y autenticación

La autenticación, las campañas versionadas, las ejecuciones, los resultados y la auditoría utilizan las cinco tablas propias `TBL_*_GC`. El portal no requiere tablas estándar de Django ni ejecuta migraciones.

Después de actualizar el código en un servidor ya instalado, vuelva a recopilar los archivos estáticos antes de reiniciar:

```powershell
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Si desea cambiar el límite de carga del Consolidado, configure `COMMERCIAL_WORKBOOK_MAX_MB` en `.env` (25 MB por defecto) y reinicie el portal.

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
