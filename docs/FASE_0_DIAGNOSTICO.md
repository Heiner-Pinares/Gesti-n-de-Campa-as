# Fase 0 — Diagnóstico del repositorio

Fecha: 02/11/2026  
Zona horaria: America/Lima  
Proyecto nuevo: `/Users/heinerpinares/Documents/Control de Campañas`  
Referencia inspeccionada en solo lectura: `/Users/heinerpinares/Documents/4DX`  
4DX: rama `main`, commit `158058c`, sin cambios locales durante la inspección.

## 1. Resultado ejecutivo

La carpeta del nuevo portal estaba vacía: no tenía framework, backend, modelos, frontend, pruebas ni configuración de base de datos.

El Portal 4DX ofrece patrones técnicos reutilizables: Python 3.12, Django 5.2, `python-oracledb` Thin, autenticación Django, templates server-rendered, pruebas con pytest y despliegue WSGI. Sin embargo, está acoplado a su propio dominio y a tablas con nombres 4DX. No se debe clonar completo ni modificar.

Se propone un proyecto Django independiente. Pueden adaptarse la construcción del DSN, la lectura segura de secretos, el login, la autorización por roles, la separación vista/servicio y las convenciones visuales. Deben excluirse las tablas y migraciones 4DX, el arranque con migración automática, el pool activado por defecto y cualquier credencial secundaria incorporada en código.

En esta fase no se abrió Oracle, no se leyó ninguna contraseña, no se ejecutó SQL y no se modificó 4DX.

## 2. Framework y versiones

El proyecto nuevo no tenía framework. El repositorio 4DX usa:

| Componente | Versión o implementación |
|---|---|
| Python | 3.12.14 |
| Django | 5.2.17 |
| Oracle driver | `oracledb` 26.0.1 |
| Frontend | Django Templates, CSS y JavaScript vanilla |
| Pruebas | pytest 9.1.1 y pytest-django 4.14.0 |
| Linux | Gunicorn 23 |
| Windows | Waitress 3 |
| Estáticos | WhiteNoise 6.12 |
| Excel | openpyxl 3.1.5 |
| Contenedores | Docker con Python 3.12 slim |

4DX contiene 101 archivos Python y 14 módulos de prueba. Oracle es su motor productivo; su batería portable usa SQLite en memoria.

## 3. Estructura relevante de 4DX

```text
4DX/
├── manage.py, run.py
├── requirements.txt, requirements.lock.txt, pytest.ini
├── .env.example, Dockerfile, docker-compose.yml
├── config/
│   ├── settings.py, test_settings.py, urls.py, wsgi.py
│   ├── database.py, runtime_secrets.py, portal_apps.py
├── compromisos/
│   ├── models.py, forms.py, views.py, urls.py
│   ├── services.py, selectors.py, permissions.py
│   ├── authentication.py, management/commands/, migrations/, tests/
├── templates/, static/, secrets/, work/
```

- `config/settings.py`: Django, base de datos, seguridad, zona horaria y logging.
- `config/database.py`: DSN, usuario proxy, secreto y pool.
- `config/runtime_secrets.py`: clave interna de Django.
- `config/portal_apps.py`: renombra tablas Django para 4DX.
- `services.py`: mutaciones y auditoría separadas de las vistas.
- `selectors.py`: consultas y cálculos.
- `permissions.py`: autorización por roles.
- `verificar_oracle.py`: conexión, versión, privilegios, tablas y migraciones.
- `run.py`: espera la base, verifica, migra, inicializa y arranca.

## 4. Configuración Oracle encontrada

4DX configura la base en `config/settings.py` mediante `config.database.database_config()`.

Patrones reutilizables:

- Oracle Thin con `python-oracledb`.
- Usuario proxy `USRFACDOC[USRVALCBIO]`.
- DSN `scan-odscbio:1521`, servicio `ODSCBIO`, servidor dedicado.
- Contraseña obtenida del entorno o de un archivo privado.
- Solo elimina CR/LF finales al leer el archivo.
- Valida el usuario proxy y el puerto.
- No usa `threaded=True`.
- Soporta pool heterogéneo para autenticación proxy.
- Usa `CONN_MAX_AGE=0` y health checks.

Ajustes obligatorios para este portal:

1. `ORACLE_POOL=false` de forma inicial.
2. Diagnóstico con `SERVICE_NAME`, `SESSION_USER`, `CURRENT_SCHEMA` y `PROXY_USER`.
3. Diagnóstico de Fase 1 estrictamente de lectura, sin exigir privilegios DDL.
4. `AUTO_MIGRATE=false`; ninguna migración sin aprobación.
5. Separar fuentes Oracle de lectura de cualquier almacenamiento futuro.
6. No reutilizar tablas como `usuarios_4dx`, `registros_portal4dx` o `registrodb_4dx`.

4DX tiene un archivo local de contraseña Oracle, pero no fue leído. El proyecto nuevo no tiene secreto. No debe copiarse automáticamente: debe provisionarse uno independiente o confirmarse el gestor corporativo autorizado.

## 5. Reutilización selectiva

| Patrón | Propuesta | Ajuste |
|---|---|---|
| Construcción del DSN y lectura del secreto | Adaptar | Pool desactivado y conexión directa inicial |
| Generación de `SECRET_KEY` | Reutilizar | Archivo fuera de Git |
| Login, sesión y CSRF | Adaptar | Branding y rutas propias |
| Roles y permisos | Adaptar | Solo Administrador y Analista inicialmente |
| Servicios transaccionales | Reutilizar el patrón | Dominio campañas/validaciones |
| Selectores/repositorios | Reutilizar el patrón | Repositorios Oracle explícitos de lectura |
| pytest + SQLite en memoria | Reutilizar | Fixtures anonimizados |
| Templates y CSS | Tomar convenciones | Menú Inicio/Campañas/Validaciones |
| Docker/WSGI | Adaptar después | Sin migración automática |

No reutilizar directamente modelos, migraciones, rutas, nombres de tablas, `.env`, secretos, respaldos, sesiones, cuentas ni `config/portal_apps.py` de 4DX.

## 6. Riesgos y hallazgos

### Crítico

La configuración de 4DX contiene una credencial secundaria como valor predeterminado en código. No se reproduce aquí. Copiar ese archivo propagaría el secreto. Debe trasladarse a un gestor de secretos o variable de entorno en una corrección separada de 4DX.

### Alto

- 4DX migra automáticamente al arrancar; es incompatible con la prohibición de DDL sin aprobación.
- 4DX activa el pool Oracle por defecto; el nuevo portal debe empezar con conexión directa.
- La cuenta proxy puede tener más privilegios de los necesarios. Debe aplicarse mínimo privilegio.
- La conectividad desde el servidor definitivo no está probada: DNS, VPN, firewall, allowlist, listener, servicio y políticas pueden bloquearla.

### Medio

- Las tablas Django de 4DX tienen nombres personalizados y producirían colisiones o acoplamiento.
- El diagnóstico 4DX comprueba privilegios de creación, no un perfil de consulta.
- Debe definirse si fuentes y resultados usarán esquemas o conexiones distintos.
- `CURRENT_SCHEMA` no se puede asumir igual a `SESSION_USER`.

### No verificado

- Compatibilidad real dentro de la red corporativa.
- Semántica de motivos y `TIPO_FILTRO`.
- Propietario y permisos de `BASE_FINAL_CAMPANA_HIST`.
- Redondeo, IGV, prorrateos, reversas y múltiples descuentos.
- Fuente confiable de la fecha de venta.

## 7. Fuentes disponibles y faltantes

Encontrados: el prompt maestro, 4DX en solo lectura y `NUEVA_MATRIZ_4DX.xlsx`, que pertenece a 4DX y no sirve como fuente de campañas.

Faltan exactamente:

1. `CFG_CAMPANAS_PORTABILIDAD.csv`
2. `Consolidado de Movil Masivo_Negocios(1).xlsx`
3. `BASE_CF_BASICO.csv`
4. Archivo con el SQL original completo

Sin ellos no es posible recalcular los 18,963 registros, verificar 11,639/6/7,318, inspeccionar columnas reales ni comparar el motor nuevo con el SQL legacy.

## 8. Fuentes por funcionalidad

| Funcionalidad | Fuente | Uso | Acceso inicial |
|---|---|---|---|
| Campañas | `USRVALCBIO.CFG_CAMPANAS_PORTABILIDAD` | Reglas existentes, estados y vigencias | Solo lectura |
| Contraste comercial | Consolidado XLSX | Campañas, planes, beneficio y vigencia | Archivo local |
| Altas/cargos | `USRVALCBIO.BASE_CF_BASICO_X` | Contratos, líneas, cargos y facturación | Solo lectura |
| Descuentos | `USRVALCBIO.BASE_CF_DESCUENTO_X` | Servicios y montos aplicados | Solo lectura |
| Motivo/fecha de alta | `ODSCLARO.CONTRACT_HISTORY` | Estado, motivo y vigencia | Solo lectura |
| Catálogo de motivos | `ODSCLARO.REASONSTATUS_ALL` | Traducir 21, 2001 y 2002 | Solo lectura |
| Campaña histórica | `BASE_FINAL_CAMPANA_HIST` | Contrato/emisión/campaña | Solo lectura; propietario pendiente |
| Regresión | `BASE_CF_BASICO.csv` | Comparación histórica anonimizada | Archivo local |
| Inicio | Configuración y futuras ejecuciones | Indicadores reales | Sin cifras ficticias |
| Auditoría | Futuras tablas aprobadas | Usuario, fecha y cambios | No crear aún |

Metadatos de Fase 1: `ALL_TABLES`, `ALL_VIEWS`, `ALL_SYNONYMS`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS`, `ALL_INDEXES`, `ALL_IND_COLUMNS` y privilegios accesibles.

## 9. Información de negocio pendiente

1. Significado oficial de `TIPO_FILTRO` para `F`, `L` y `S`.
2. Operación de `2001` y confirmación de `21` y `2002`.
3. Fecha de elegibilidad y fuente real de fecha de venta.
4. Prioridad cuando coinciden varias reglas.
5. Inclusividad de los límites de plan.
6. Base con IGV o sin IGV.
7. Precisión, tolerancia y redondeo.
8. Tratamiento de `CF_ADEL`, `CF_PRO`, `CF_DEV`, prorrateos, ajustes y reversas.
9. Normalización del signo de descuentos.
10. Identificador fiable del servicio de descuento.
11. Múltiples descuentos por contrato/fecha.
12. Inicio, consumo y fin de los meses de beneficio.
13. Canales, excepciones e identificadores PEO.
14. Permisos para ejecutar, editar, ver contrato/línea y exportar.
15. Frecuencia, horario, zona horaria e infraestructura de automatización.
16. Esquema y nombres finales de objetos nuevos.

Los casos afectados deben quedar `POR REVISAR` o como pruebas pendientes, nunca `CORRECTO` por suposición.

## 10. Arquitectura propuesta

```text
Navegador
  └─ Django Templates + vistas autenticadas
       ├─ Servicio de campañas
       ├─ Servicio de ejecuciones
       └─ Motor de validación
            ├─ Selección de versión/regla
            ├─ Cálculo Decimal
            ├─ Clasificación explicable
            └─ Evidencias normalizadas
       ├─ Repositorios Oracle de solo lectura
       └─ Persistencia propia, solo tras aprobar modelo y DDL
```

La ejecución manual y la futura programada deben usar el mismo servicio. La solicitud HTTP no debe ejecutar una validación larga dentro de la respuesta.

## 11. Estructura prevista

```text
Control de Campañas/
├── manage.py, requirements.txt, requirements.lock.txt, pytest.ini
├── .env.example, .gitignore
├── config/
│   ├── settings.py, test_settings.py, urls.py, wsgi.py
│   ├── database.py, runtime_secrets.py
├── portal/
│   ├── permissions.py, authentication.py, context_processors.py
├── campanas/
│   ├── forms.py, views.py, urls.py, services.py, selectors.py, tests/
├── validaciones/
│   ├── domain/{models,money,rule_matching,classifier}.py
│   ├── repositories/{oracle_metadata,oracle_sources,result_store}.py
│   ├── services/{engine,executions}.py
│   ├── management/commands/
│   │   ├── verificar_oracle.py, inspeccionar_oracle.py, validar_campanas.py
│   ├── views.py, urls.py, tests/
├── templates/, static/, fixtures/, docs/, secrets/
```

No se crearán modelos persistentes del dominio hasta aprobar metadatos, análisis funcional y modelo.

## 12. Plan incremental verificable

### Cambio 1 — Esqueleto seguro

- Crear Django independiente, `.gitignore` y `.env.example`.
- SQLite en memoria para pruebas.
- `ORACLE_POOL=false` y `AUTO_MIGRATE=false`.
- Pruebas de configuración y secretos.

Verificación: `python manage.py check` y pruebas unitarias sin Oracle.

### Cambio 2 — Conexión y diagnóstico de lectura

- Oracle Thin directo.
- Informar servicio, sesión, esquema y proxy.
- Clasificar errores sin exponer credenciales.
- No exigir permisos DDL.

Verificación: diagnóstico autorizado desde la red corporativa.

### Cambio 3 — Inventario de metadatos

- Objetos, columnas, claves, índices, sinónimos y privilegios.
- Informe sanitizado; sin DDL ni DML.

### Cambio 4 — Análisis funcional

- Inspeccionar tres archivos y SQL original.
- Recalcular conteos y documentar reglas.
- Matriz de diferencias anonimizada.

### Cambio 5 — Motor puro

- Selección de reglas, `Decimal` y clasificación explicable.
- Sin depender de tablas nuevas.
- Pruebas para casos confirmados.

### Cambio 6 — Portal de consulta

- Inicio, Campañas y Validaciones.
- Estados vacíos reales, filtros, paginación, permisos y responsive.

### Punto de aprobación — Modelo y DDL

Presentar entidades mínimas, DDL, esquema, privilegios, índices, claves y auditoría. No persistir sin aprobación explícita.

### Cambio 7 — Edición y persistencia autorizadas

- Versionar campañas y auditar cambios.
- Guardar ejecuciones/resultados idempotentes.

### Cambio 8 — Ejecución asíncrona y comando

- Un servicio para botón y comando.
- Prevención de duplicados y reproceso seguro.
- Sin registrar todavía una tarea real.

### Cambio 9 — Automatización y despliegue

- Control-M o Windows Task Scheduler solo tras confirmar horario, zona e infraestructura.
- Validación en servidor definitivo.

## 13. Entrega de Fase 0

Archivos creados:

- `README.md`
- `docs/FASE_0_DIAGNOSTICO.md`

Comprobaciones realizadas:

- Inventario con `find` y `rg`.
- Git de solo lectura para estado y commit de 4DX.
- Lectura de configuración, dependencias, autenticación, permisos, modelos, servicios y pruebas.
- Consulta de versiones de Python, Django y `oracledb`.
- Verificación de existencia, sin lectura, de secretos y fuentes solicitadas.

No se ejecutaron servidores, migraciones, pruebas Oracle, conexiones de red, DDL, DML ni tareas programadas.

## 14. Próximo paso recomendado

Continuar con el Cambio 1 y proporcionar los cuatro insumos faltantes. La conexión de Fase 1 debe hacerse solo cuando el proyecto tenga su propio secreto provisionado y se confirme la autorización de cuenta y origen de red.
