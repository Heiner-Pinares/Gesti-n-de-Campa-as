# Producción permanente en Windows

Esta es la guía vigente para operar el portal con Waitress sin depender de una
consola abierta. Los scripts no ejecutan migraciones, no autentican usuarios
reales contra Active Directory y no modifican el Firewall de Windows.

## Arquitectura efectiva

- Django sirve la aplicación WSGI con Waitress.
- Oracle ODSCBIO es la base de datos real. Las fuentes se consultan y los
  resultados se escriben únicamente en las tablas propias `TBL_*_GC`.
- Active Directory se usa mediante LDAP/NTLM. La validación de publicación solo
  comprueba TCP 389 o 636, `ldap3` y MD4; no solicita credenciales de dominio.
- WhiteNoise sirve los archivos recopilados desde `staticfiles`, una salida
  exclusiva distinta de la fuente `static`.
- `scripts\portal.ps1` administra el proceso, su PID verificado, metadatos y
  logs UTF-8 en `logs\portal`.
- Task Scheduler ejecuta `portal.ps1 start` al arrancar Windows con la cuenta de
  servicio aprobada.

## Puerto y dirección de escucha

La única fuente normal del puerto es `.env`. Se aceptan, en este orden:

1. `PORTAL_PORT` (nombre preferido).
2. `PORT` (compatibilidad con instalaciones existentes).
3. `WEB_PORT` (compatibilidad histórica).
4. `8000` únicamente como valor predeterminado si ninguna variable existe.

Por tanto, si el servidor ya tiene `PORT=8006`, no hay que cambiarlo: todos los
comandos usarán el puerto 8006. Un parámetro explícito `-Port` solo lo anula para
esa ejecución.

La dirección debe ser `WEB_BIND_ADDRESS=0.0.0.0`; también se conservan los
alias `HOST` y `WEB_HOST`. `0.0.0.0` es la dirección de escucha, no una URL para
el usuario.

Ejemplo preferido para una instalación nueva:

```dotenv
WEB_BIND_ADDRESS=0.0.0.0
PORTAL_PORT=8006
PORTAL_THREADS=8
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,172.19.194.219,LIMDOCFACTV02
AUTO_MIGRATE=false
```

`127.0.0.1` o `localhost` debe permanecer en `ALLOWED_HOSTS` para la prueba de
salud local. `ALLOWED_HOSTS=*` funciona en una prueba inicial, pero genera una
advertencia y debe limitarse antes del cierre de producción.

## Comandos diarios

Ejecute desde la raíz del proyecto:

```powershell
.\scripts\portal.cmd validate
.\scripts\portal.cmd start
.\scripts\portal.cmd status
.\scripts\portal.cmd logs
.\scripts\portal.cmd restart
.\scripts\portal.cmd stop
```

Opcionalmente, `logs` acepta el número de líneas:

```powershell
.\scripts\portal.cmd logs -Tail 250
```

El administrador hace lo siguiente:

- `start`: rechaza un puerto ocupado, ejecuta la validación, inicia Waitress en
  segundo plano, registra el PID y espera una respuesta HTTP local.
- `stop`: lee el PID y compara tanto el ejecutable como la línea de comandos con
  el Python y `run.py` absolutos del proyecto. Nunca termina procesos por nombre.
- `restart`: usa exactamente el cierre seguro anterior y vuelve a validar.
- `status`: informa PID, puerto, URL local y detecta archivos PID obsoletos.
- `logs`: muestra los últimos logs estándar y de error de la ejecución vigente.
- `validate`: ejecuta comprobaciones sin migrar ni modificar el esquema.

Si un PID fue reutilizado por otro proceso, el administrador limpia solamente
su referencia obsoleta y deja intacto el proceso ajeno.

## Qué valida antes de iniciar

Los errores bloquean el inicio; las advertencias se muestran por separado.

- `.venv`, Django, Waitress, WhiteNoise, Oracle, OpenPyXL, `ldap3` y
  `pycryptodome/MD4`.
- `.env`, `DEBUG=False`, `ALLOWED_HOSTS` y migraciones automáticas deshabilitadas.
- Conexión real Oracle, sesión proxy y compatibilidad de `TBL_*_GC`.
- Conectividad TCP al host LDAP en 389 o 636, sin autenticación real.
- Puerto libre en `0.0.0.0`.
- Escritura en `logs`, `runtime-config` y `STATIC_ROOT`.
- `STATIC_ROOT` separado de `STATICFILES_DIRS` y `collectstatic` correcto.
- Ausencia de cambios de modelos que exigirían una migración no aprobada.

Se advierte, sin bloquear, por LDAP plano, HTTP interno, `ALLOWED_HOSTS=*`, una
versión de Python distinta de 3.12 y la ausencia deliberada de correo SMTP.

## Registro automático al arrancar Windows

Abra PowerShell como administrador y use valores aprobados por Infraestructura:

```powershell
.\scripts\publicar_portal_windows.ps1 `
  -ServiceAccount "DOMINIO\cuenta_servicio" `
  -PublicUrl "http://172.19.194.219:8006/" `
  -TaskName "Control de Campañas - Portal" `
  -AllowInternalHttp
```

No hace falta pasar `-Port 8006` si `.env` ya contiene `PORT=8006` o
`PORTAL_PORT=8006`. Si se pasa `-Port`, el script exige que coincida con la URL.

El publicador:

1. Exige elevación administrativa.
2. Valida URL, puerto, `ALLOWED_HOSTS`, configuración y conexiones.
3. Solicita la contraseña con `Read-Host -AsSecureString`.
4. Registra primero una tarea temporal para comprobar cuenta y credenciales.
5. Registra o actualiza la tarea definitiva con disparador `AtStartup`.
6. Inicia la tarea y espera una respuesta HTTP local.
7. Borra de memoria el BSTR de la contraseña y nunca la escribe en archivos,
   argumentos persistentes ni logs.

Para HTTP se exige `-AllowInternalHttp`. Para una URL HTTPS se exige
`COOKIE_SECURE=true`, `TRUST_PROXY_HTTPS=true`, el origen en
`CSRF_TRUSTED_ORIGINS` y un proxy TLS corporativo. Waitress no termina TLS por sí
solo.

## Red y Firewall

Los scripts nunca crean reglas. Infraestructura debe autorizar por separado el
acceso entrante al puerto seleccionado solo en los perfiles y segmentos
corporativos necesarios. No se debe exponer Waitress directamente a Internet ni
abrir Oracle 1521 a los usuarios del portal.

La URL final es:

```text
http(s)://<IP_O_DNS_APROBADO>:<PUERTO_DEL_ENV>/
```

Con el dato de despliegue indicado en esta instalación, la candidata interna es
`http://172.19.194.219:8006/`; debe confirmarse que esa IP siga asignada al
servidor y que Infraestructura haya autorizado el acceso.

## Actualización y reversión

Antes de actualizar, conserve el commit o ZIP anterior y respalde `.env`,
`secrets`, `runtime-config` y el Consolidado. No copie secretos al repositorio.

```powershell
.\scripts\portal.cmd stop
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\scripts\portal.cmd validate
.\scripts\portal.cmd start
.\scripts\portal.cmd status
```

No ejecute `manage.py migrate`. Para revertir código, detenga el portal, restaure
la versión anterior mediante el procedimiento Git/ZIP aprobado, reinstale su
`requirements.lock.txt`, valide e inicie. Las tablas Oracle no deben eliminarse
ni recrearse durante una reversión de aplicación.

## Datos aún necesarios para la publicación definitiva

- Cuenta de servicio Windows autorizada.
- Nombre definitivo de la tarea programada.
- IP o DNS público interno definitivo y confirmación de que corresponde al
  servidor.
- Aprobación de HTTP interno o datos del proxy HTTPS corporativo.
- Regla de red/firewall administrada por Infraestructura, si todavía no existe.
