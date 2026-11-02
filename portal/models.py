"""Modelos Oracle del portal. El DDL se administra fuera de migraciones automáticas."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class PortalUserManager(BaseUserManager):
    use_in_migrations = False

    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)

    def create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("El usuario es obligatorio.")
        if not password:
            raise ValueError("La contraseña es obligatoria.")
        user = self.model(username=username.strip().upper(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db, force_insert=True)
        return user


class PortalUser(AbstractBaseUser):
    ROLE_ADMIN = "ADMINISTRADOR"
    ROLE_ANALYST = "ANALISTA"
    ROLE_CHOICES = ((ROLE_ADMIN, "Administrador"), (ROLE_ANALYST, "Analista"))

    id_usuario = models.BigAutoField(primary_key=True, db_column="ID_USUARIO")
    username = models.CharField(max_length=80, unique=True, db_column="USUARIO")
    nombre_completo = models.CharField(max_length=150, db_column="NOMBRE_COMPLETO")
    email = models.EmailField(max_length=254, blank=True, null=True, db_column="EMAIL")
    password = models.CharField(max_length=128, db_column="CLAVE_HASH")
    rol = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST, db_column="ROL")
    is_active = models.BooleanField(default=True, db_column="ACTIVO")
    last_login = models.DateTimeField(blank=True, null=True, db_column="ULTIMO_ACCESO")
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column="FECHA_CREACION")
    fecha_modificacion = models.DateTimeField(auto_now=True, db_column="FECHA_MODIFICACION")

    objects = PortalUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["nombre_completo"]

    class Meta:
        managed = False
        db_table = "TBL_USUARIO_GC"
        verbose_name = "usuario del portal"
        verbose_name_plural = "usuarios del portal"

    @property
    def is_staff(self):
        return self.rol == self.ROLE_ADMIN

    @property
    def is_superuser(self):
        return self.rol == self.ROLE_ADMIN

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombre_completo.split()[0] if self.nombre_completo else self.username

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_staff

    def has_module_perms(self, app_label):
        return self.is_active and self.is_staff

    def __str__(self):
        return self.username


class CampaignVersion(models.Model):
    BENEFIT_PERCENTAGE = "PORCENTAJE"
    BENEFIT_FIXED = "MONTO_FIJO"

    id_version = models.BigAutoField(primary_key=True, db_column="ID_VERSION")
    id_campana_origen = models.DecimalField(max_digits=38, decimal_places=0, blank=True, null=True, db_column="ID_CAMPANA_ORIGEN")
    version = models.PositiveIntegerField(default=1, db_column="VERSION")
    cod_plan = models.CharField(max_length=10, blank=True, null=True, db_column="COD_PLAN")
    nombre_campana = models.CharField(max_length=400, db_column="NOMBRE_CAMPANA")
    plan_minimo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="PLAN_MINIMO")
    plan_maximo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="PLAN_MAXIMO")
    escenario = models.CharField(max_length=100, db_column="ESCENARIO")
    tipo_beneficio = models.CharField(max_length=20, db_column="TIPO_BENEFICIO")
    valor_beneficio = models.DecimalField(max_digits=12, decimal_places=4, db_column="VALOR_BENEFICIO")
    periodo_meses = models.PositiveIntegerField(blank=True, null=True, db_column="PERIODO_MESES")
    tipo_filtro = models.CharField(max_length=10, blank=True, null=True, db_column="TIPO_FILTRO")
    dia_ini = models.PositiveSmallIntegerField(blank=True, null=True, db_column="DIA_INI")
    dia_fin = models.PositiveSmallIntegerField(blank=True, null=True, db_column="DIA_FIN")
    vigencia_ini = models.DateField(db_column="VIGENCIA_INI")
    vigencia_fin = models.DateField(db_column="VIGENCIA_FIN")
    estado = models.CharField(max_length=1, default="A", db_column="ESTADO")
    descripcion = models.CharField(max_length=400, blank=True, null=True, db_column="DESCRIPCION")
    condiciones_json = models.TextField(blank=True, null=True, db_column="CONDICIONES_JSON")
    usuario_creacion = models.ForeignKey(PortalUser, models.PROTECT, db_column="ID_USUARIO_CREACION", related_name="campanas_creadas")
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column="FECHA_CREACION")
    fecha_modificacion = models.DateTimeField(auto_now=True, db_column="FECHA_MODIFICACION")

    class Meta:
        managed = False
        db_table = "TBL_CAMPANA_VERSION_GC"


class ValidationExecution(models.Model):
    id_ejecucion = models.BigAutoField(primary_key=True, db_column="ID_EJECUCION")
    fecha_desde = models.DateField(db_column="FECHA_DESDE")
    fecha_hasta = models.DateField(db_column="FECHA_HASTA")
    tipo_ejecucion = models.CharField(max_length=15, db_column="TIPO_EJECUCION")
    estado = models.CharField(max_length=20, default="PENDIENTE", db_column="ESTADO")
    parametros_json = models.TextField(blank=True, null=True, db_column="PARAMETROS_JSON")
    total_evaluados = models.PositiveBigIntegerField(default=0, db_column="TOTAL_EVALUADOS")
    total_correctos = models.PositiveBigIntegerField(default=0, db_column="TOTAL_CORRECTOS")
    total_errores = models.PositiveBigIntegerField(default=0, db_column="TOTAL_ERRORES")
    total_revisar = models.PositiveBigIntegerField(default=0, db_column="TOTAL_REVISAR")
    total_no_aplica = models.PositiveBigIntegerField(default=0, db_column="TOTAL_NO_APLICA")
    mensaje_error = models.CharField(max_length=1000, blank=True, null=True, db_column="MENSAJE_ERROR")
    usuario_ejecucion = models.ForeignKey(PortalUser, models.PROTECT, db_column="ID_USUARIO_EJECUCION", blank=True, null=True, related_name="ejecuciones")
    fecha_solicitud = models.DateTimeField(auto_now_add=True, db_column="FECHA_SOLICITUD")
    fecha_inicio = models.DateTimeField(blank=True, null=True, db_column="FECHA_INICIO")
    fecha_fin = models.DateTimeField(blank=True, null=True, db_column="FECHA_FIN")

    class Meta:
        managed = False
        db_table = "TBL_VALIDACION_EJECUCION_GC"


class ValidationStoredResult(models.Model):
    id_resultado = models.BigAutoField(primary_key=True, db_column="ID_RESULTADO")
    ejecucion = models.ForeignKey(ValidationExecution, models.CASCADE, db_column="ID_EJECUCION", related_name="resultados")
    version = models.ForeignKey(CampaignVersion, models.PROTECT, db_column="ID_VERSION", blank=True, null=True, related_name="resultados")
    invoice_id = models.DecimalField(max_digits=38, decimal_places=0, blank=True, null=True, db_column="INVOICE_ID")
    invoicing_date = models.DateField(blank=True, null=True, db_column="INVOICING_DATE")
    co_id = models.DecimalField(max_digits=38, decimal_places=0, blank=True, null=True, db_column="CO_ID")
    linea = models.CharField(max_length=30, blank=True, null=True, db_column="LINEA")
    ch_reason = models.DecimalField(max_digits=38, decimal_places=0, blank=True, null=True, db_column="CH_REASON")
    plan_monto = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="PLAN_MONTO")
    descuento_esperado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="DESCUENTO_ESPERADO")
    descuento_aplicado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="DESCUENTO_APLICADO")
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, db_column="DIFERENCIA")
    clasificacion = models.CharField(max_length=20, db_column="CLASIFICACION")
    codigo_motivo = models.CharField(max_length=50, blank=True, null=True, db_column="CODIGO_MOTIVO")
    descripcion_motivo = models.CharField(max_length=1000, db_column="DESCRIPCION_MOTIVO")
    evidencia_json = models.TextField(blank=True, null=True, db_column="EVIDENCIA_JSON")
    fecha_registro = models.DateTimeField(auto_now_add=True, db_column="FECHA_REGISTRO")

    class Meta:
        managed = False
        db_table = "TBL_VALIDACION_RESULTADO_GC"


class ChangeAudit(models.Model):
    id_auditoria = models.BigAutoField(primary_key=True, db_column="ID_AUDITORIA")
    entidad = models.CharField(max_length=50, db_column="ENTIDAD")
    id_entidad = models.DecimalField(max_digits=38, decimal_places=0, db_column="ID_ENTIDAD")
    accion = models.CharField(max_length=20, db_column="ACCION")
    valor_anterior_json = models.TextField(blank=True, null=True, db_column="VALOR_ANTERIOR_JSON")
    valor_nuevo_json = models.TextField(blank=True, null=True, db_column="VALOR_NUEVO_JSON")
    usuario = models.ForeignKey(PortalUser, models.PROTECT, db_column="ID_USUARIO", blank=True, null=True, related_name="auditorias")
    direccion_ip = models.GenericIPAddressField(blank=True, null=True, db_column="DIRECCION_IP")
    fecha_evento = models.DateTimeField(auto_now_add=True, db_column="FECHA_EVENTO")

    class Meta:
        managed = False
        db_table = "TBL_AUDITORIA_CAMBIO_GC"
