# Portal de Control de Campañas y Descuentos — Móvil Masivo

Proyecto independiente para administrar campañas comerciales y validar descuentos de Móvil Masivo sobre Oracle ODSCBIO.

## Estado

- Fase 0: diagnóstico completado.
- Fase 1: conexión y metadatos Oracle comprobados en el servidor Windows.
- Fase 2: análisis local de CSV, XLSX y SQL legacy completado.
- Fase 3: modelo persistente Oracle aprobado e implementado con nomenclatura `TBL_*_GC`.
- Fases 4 y 5: motor parametrizable, ejecución manual, historial, resultados y exportación implementados.
- Fase 6: operación permanente con Waitress, administrador de proceso y publicación segura en Windows implementados.

El portal no ejecuta migraciones ni DDL al iniciar. La creación del esquema se realiza solamente mediante el comando explícito documentado para Windows.

Documentación principal:

- `docs/FASE_0_DIAGNOSTICO.md`
- `docs/FASE_1_IMPLEMENTACION_SEGURA.md`
- `docs/FASE_2_ANALISIS_FUENTES_Y_SQL.md`
- `docs/SERVIDOR_WINDOWS.md`
- `docs/PRODUCCION_WINDOWS.md`
- `docs/MOTOR_VALIDACION.md`
- `docs/MANUAL_USUARIO.md`

## Arquitectura propuesta

- Python 3.12 y Django 5.2 en un proyecto independiente.
- Django Templates, CSS y JavaScript vanilla.
- `python-oracledb` Thin, inicialmente sin pool.
- Oracle en lectura para las fuentes de facturación y con escritura limitada a las tablas propias `TBL_*_GC`.
- Autenticación corporativa Claro por LDAP/NTLM para cuentas C/E y autenticación
  local restringida para los demás usuarios, ambas sobre `TBL_USUARIO_GC`.
- Sesiones firmadas en cookies HttpOnly, sin tablas estándar `AUTH_*` ni tablas LDAP nuevas.
- Reutilización selectiva de patrones de 4DX, sin modificar ni copiar sus tablas, datos, secretos o migraciones.
- Pruebas portables con SQLite en memoria y fixtures anonimizados.

## Instalación resumida en Windows

1. Configure `.env` y `secrets\oracle_password.txt`.
2. Ejecute `scripts\setup_windows.ps1`.
3. Compruebe la conexión con `scripts\check_oracle.ps1`.
4. Revise `sql\oracle\001_create_tables_gc.sql` y `scripts\preview_oracle_schema.ps1`.
5. Cree los objetos autorizados con `scripts\apply_oracle_schema.ps1`.
6. Cree el administrador con `scripts\create_portal_admin.ps1`.
7. Valide e inicie el portal mediante `scripts\portal.cmd validate` y `scripts\portal.cmd start`.

Las cuentas `C`/`E` se crean o sincronizan automáticamente después de validar su
contraseña con Dominio Claro. La contraseña de dominio no se almacena en Oracle.
El atributo AD `title` se sincroniza como puesto laboral, separado del rol de
permisos del portal.
La configuración y los pasos de actualización están en
`docs/SERVIDOR_WINDOWS.md`, sección **Active Directory de Claro**.

## Operación de producción en Windows

El puerto se obtiene de `PORTAL_PORT` o del alias compatible `PORT` en `.env`.
Si ya está configurado `PORT=8006`, no es necesario repetirlo en los comandos.
La escucha debe permanecer en `WEB_BIND_ADDRESS=0.0.0.0` (también se admite
`HOST`).

```powershell
.\scripts\portal.cmd validate
.\scripts\portal.cmd start
.\scripts\portal.cmd status
.\scripts\portal.cmd logs
.\scripts\portal.cmd restart
.\scripts\portal.cmd stop
```

Los logs UTF-8 quedan en `logs\portal` y el PID/metadatos en
`runtime-config\portal`; ambas ubicaciones son exclusivas de este proyecto. Para
registrar el inicio automático, abra PowerShell como administrador:

```powershell
.\scripts\publicar_portal_windows.ps1 `
  -ServiceAccount "DOMINIO\CUENTA_REAL" `
  -PublicUrl "http://IP_DEL_SERVIDOR:8006/" `
  -TaskName "Control de Campañas - Inicio automático" `
  -AllowInternalHttp
```

El publicador solicita la contraseña de manera oculta, valida Oracle, esquema,
LDAP TCP, MD4, permisos, estáticos y respuesta HTTP, y no modifica el Firewall.
Para HTTPS mediante proxy configure `COOKIE_SECURE=true`,
`TRUST_PROXY_HTTPS=true` y `CSRF_TRUSTED_ORIGINS`. Para migrar LDAP de `plano` a
`starttls` o `ldaps`, cambie `LDAP_MODO` y configure `LDAP_CA_CERT` con la CA que
entregue TI. Los rechazos de credenciales se muestran al usuario sin detalles
internos; una caída de AD se distingue y se diagnostica en los logs sin registrar
contraseñas.

La guía completa, incluidos instalación, actualización y reversión, está en
`docs/PRODUCCION_WINDOWS.md`.

Una validación también puede ejecutarse sin abrir el portal:

```powershell
.\scripts\run_campaign_validation.ps1 -Desde 2026-10-24 -Hasta 2026-10-27
```

No se debe copiar el secreto de 4DX ni ejecutar `manage.py migrate`.

El arranque de Windows usa Waitress en `0.0.0.0` y toma el puerto de
`PORTAL_PORT` o, por compatibilidad, de `PORT` en `.env`. El administrador
comprueba Oracle, LDAP TCP, dependencias, permisos y archivos estáticos. No
publica Oracle, no ejecuta migraciones y no modifica el Firewall de Windows.
