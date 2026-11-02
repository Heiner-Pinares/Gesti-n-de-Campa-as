from decimal import Decimal

from django import forms


class CampaignForm(forms.Form):
    BENEFIT_CHOICES = (
        ("PORCENTAJE", "Porcentaje"),
        ("MONTO_FIJO", "Monto fijo en soles"),
    )
    STATUS_CHOICES = (("A", "Activa"), ("I", "Inactiva"))

    identificador_comercial = forms.CharField(max_length=10, required=False)
    nombre_campana = forms.CharField(max_length=400)
    operacion = forms.CharField(max_length=100)
    plan_minimo = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    plan_maximo = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    tipo_beneficio = forms.ChoiceField(choices=BENEFIT_CHOICES)
    valor_beneficio = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    periodo_meses = forms.IntegerField(min_value=1, max_value=120)
    vigencia_ini = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    vigencia_fin = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    estado = forms.ChoiceField(choices=STATUS_CHOICES)
    descripcion = forms.CharField(max_length=400, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    tipo_filtro = forms.CharField(max_length=10, required=False)
    dia_ini = forms.IntegerField(min_value=1, max_value=31, required=False)
    dia_fin = forms.IntegerField(min_value=1, max_value=31, required=False)
    motivo_modificacion = forms.CharField(
        max_length=400,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, require_reason=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_reason = require_reason
        if require_reason:
            self.fields["motivo_modificacion"].required = True

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get("plan_minimo")
        maximum = cleaned.get("plan_maximo")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("plan_maximo", "El plan máximo no puede ser menor al mínimo.")

        start = cleaned.get("vigencia_ini")
        end = cleaned.get("vigencia_fin")
        if start and end and start > end:
            self.add_error("vigencia_fin", "La fecha final no puede ser anterior a la inicial.")

        value = cleaned.get("valor_beneficio")
        if cleaned.get("tipo_beneficio") == "PORCENTAJE" and value is not None:
            if value <= Decimal("0") or value > Decimal("100"):
                self.add_error("valor_beneficio", "El porcentaje debe ser mayor que 0 y máximo 100.")
        return cleaned


class ValidationRunForm(forms.Form):
    desde = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, max_days=31, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_days = max_days

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("desde")
        end = cleaned.get("hasta")
        if start and end:
            if start > end:
                self.add_error("hasta", "La fecha final no puede ser anterior a la inicial.")
            elif (end - start).days + 1 > self.max_days:
                self.add_error(
                    "hasta",
                    f"El periodo máximo por ejecución es de {self.max_days} días.",
                )
        return cleaned
