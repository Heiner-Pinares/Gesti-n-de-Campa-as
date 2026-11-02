# Fase 1 — Preparación segura y conexión Oracle

## Implementado

- Proyecto independiente con Python 3.12 y Django 5.2.
- Configuración Oracle Thin con `python-oracledb`.
- Lectura del secreto desde entorno o archivo local excluido de Git.
- `ORACLE_POOL=false` por defecto.
- `AUTO_MIGRATE=false` y ausencia de migraciones automáticas en el arranque.
- Comando `verificar_oracle` de solo lectura.
- Consulta de diagnóstico con servicio, usuario de sesión, esquema y proxy.
- Errores comprensibles para ORA-01017, ORA-12154, ORA-12514, ORA-12541, ORA-28000 y ORA-20001.
- Scripts PowerShell y Waitress para la futura instalación Windows.
- Portal inicial autenticado con Inicio, Campañas y Validaciones.
- Campañas en modo lectura desde CSV hasta aprobar persistencia.
- Motor puro inicial para porcentajes, montos fijos, ambigüedad y datos faltantes.

## Verificación portable

```text
python manage.py check: sin observaciones
pytest: 19 pruebas aprobadas
```

También se revisaron visualmente Inicio y Campañas. Los porcentajes almacenados como fracciones se presentan como 30% y 50% sin modificar el valor fuente.

## No ejecutado

- No se abrió una conexión Oracle.
- No se ejecutó el SQL legacy.
- No se consultaron metadatos Oracle.
- No se crearon tablas.
- No se ejecutaron migraciones.
- No se instaló un servicio Windows.
- No se programó ninguna tarea.

## Bloqueo de la conexión real

Se necesita provisionar el secreto específico de este proyecto y confirmar autorización de la cuenta y del origen de red. Después se puede ejecutar en el servidor Windows:

```powershell
.\scripts\check_oracle.ps1
```
