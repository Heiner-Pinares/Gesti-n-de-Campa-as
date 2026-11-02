import csv
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from validaciones.service import (
    DuplicateExecution,
    create_execution,
    parse_evidence,
    start_background_execution,
)

from .campaign_service import (
    CampaignConflict,
    CampaignNotFound,
    campaign_form_initial,
    campaign_history,
    get_campaign,
    list_effective_campaigns,
    save_campaign,
)
from .forms import CampaignForm, ValidationRunForm
from .models import ValidationExecution, ValidationStoredResult
from .permissions import administrator_required
from .source_csv import CampaignSourceUnavailable


STATUS_LABELS = {
    "PENDIENTE": "Pendiente",
    "EN_PROCESO": "En ejecución",
    "COMPLETADA": "Completada",
    "ERROR": "Fallida",
}


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def _decimal_text(value):
    if value is None:
        return "—"
    return f"{Decimal(value):,.2f}"


def _campaign_display(record):
    row = dict(record)
    if row["benefit_type"] == "PORCENTAJE" and row["benefit_value"] is not None:
        row["benefit_display"] = f"{row['benefit_value'] * 100:g}%"
    elif row["benefit_type"] == "MONTO_FIJO" and row["benefit_value"] is not None:
        row["benefit_display"] = f"S/ {_decimal_text(row['benefit_value'])}"
    else:
        row["benefit_display"] = "Pendiente de parametrizar"
    row["plan_display"] = f"S/ {_decimal_text(row['plan_min'])} – S/ {_decimal_text(row['plan_max'])}"
    row["status_display"] = "Activa" if row["active"] else "Inactiva"
    return row


def _masked(value):
    text = str(value or "")
    if not text:
        return "—"
    return "•" * max(0, len(text) - 4) + text[-4:]


def _execution_context(execution):
    if not execution:
        return None
    execution.status_label = STATUS_LABELS.get(execution.estado, execution.estado)
    execution.is_active_run = execution.estado in {"PENDIENTE", "EN_PROCESO"}
    return execution


@login_required
def inicio(request):
    campaign_error = None
    try:
        campaigns = list_effective_campaigns(settings)
        active_count = sum(item["active"] for item in campaigns)
        source_state = "Disponible"
    except (CampaignSourceUnavailable, DatabaseError) as error:
        active_count = None
        source_state = "No disponible"
        campaign_error = str(error)
    try:
        latest = _execution_context(
            ValidationExecution.objects.order_by("-fecha_solicitud", "-id_ejecucion").first()
        )
    except DatabaseError:
        latest = None
    return render(
        request,
        "portal/inicio.html",
        {
            "title": "Inicio",
            "active_count": active_count,
            "source_state": source_state,
            "campaign_error": campaign_error,
            "latest": latest,
        },
    )


@login_required
def campanas(request):
    query = request.GET.get("q", "").strip().casefold()
    operation = request.GET.get("operacion", "").strip()
    status = request.GET.get("estado", "").strip()
    error = None
    records = []
    try:
        records = list_effective_campaigns(settings)
        if query:
            records = [
                item for item in records
                if query in f"{item['origin_id']} {item['name']} {item['cod_plan']}".casefold()
            ]
        if operation:
            records = [item for item in records if item["operation"] == operation]
        if status:
            records = [item for item in records if item["active"] == (status == "A")]
    except (CampaignSourceUnavailable, DatabaseError) as exc:
        error = str(exc)
    operations = sorted({item["operation"] for item in records if item["operation"]})
    page = Paginator([_campaign_display(item) for item in records], 25).get_page(
        request.GET.get("pagina")
    )
    return render(
        request,
        "portal/campanas.html",
        {
            "title": "Campañas",
            "page": page,
            "error": error,
            "q": request.GET.get("q", ""),
            "operation": operation,
            "operations": operations,
            "status": status,
        },
    )


@administrator_required
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            created = save_campaign(
                settings, form.cleaned_data, request.user, ip_address=_client_ip(request)
            )
        except CampaignConflict as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "La campaña se creó y quedó registrada en auditoría.")
            return redirect("campaign_edit", record_key=f"V-{created.pk}")
    return render(
        request,
        "portal/campaign_form.html",
        {"title": "Nueva campaña", "form": form, "record": None, "history": []},
    )


@administrator_required
def campaign_edit(request, record_key):
    try:
        record = get_campaign(settings, record_key)
    except CampaignNotFound as error:
        raise Http404(str(error)) from error
    form = CampaignForm(
        request.POST or None,
        initial=campaign_form_initial(record),
        require_reason=True,
    )
    if request.method == "POST" and form.is_valid():
        try:
            created = save_campaign(
                settings,
                form.cleaned_data,
                request.user,
                previous=record,
                ip_address=_client_ip(request),
            )
        except CampaignConflict as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Se guardó la versión {created.version} de la campaña.")
            return redirect("campaign_edit", record_key=f"V-{created.pk}")
    return render(
        request,
        "portal/campaign_form.html",
        {
            "title": "Ver / editar campaña",
            "form": form,
            "record": _campaign_display(record),
            "history": campaign_history(record["origin_id"]),
        },
    )


def _result_display(item, show_sensitive):
    evidence = parse_evidence(item.evidencia_json)
    return {
        "id": item.pk,
        "contract": str(item.co_id or "—") if show_sensitive else _masked(item.co_id),
        "line": str(item.linea or "—") if show_sensitive else _masked(item.linea),
        "operation": evidence.get("operacion") or "Sin identificar",
        "campaign": evidence.get("campana") or (
            item.version.nombre_campana if item.version_id else "Sin identificar"
        ),
        "plan": item.plan_monto,
        "expected": item.descuento_esperado,
        "applied": item.descuento_aplicado,
        "difference": item.diferencia,
        "classification": item.clasificacion,
        "reason": item.descripcion_motivo,
        "evidence": evidence,
        "object": item,
    }


@login_required
def validaciones(request):
    executions = list(
        ValidationExecution.objects.select_related("usuario_ejecucion")
        .order_by("-fecha_solicitud", "-id_ejecucion")[:30]
    )
    selected = None
    selected_id = request.GET.get("ejecucion")
    if selected_id:
        selected = get_object_or_404(ValidationExecution, pk=selected_id)
    elif executions:
        selected = executions[0]
    selected = _execution_context(selected)

    classification = request.GET.get("resultado", "").strip()
    operation = request.GET.get("operacion", "").strip()
    campaign = request.GET.get("campana", "").strip()
    identifier = request.GET.get("identificador", "").strip()
    result_rows = []
    operations = set()
    campaigns = set()
    if selected:
        queryset = ValidationStoredResult.objects.filter(ejecucion=selected).select_related("version")
        if classification:
            queryset = queryset.filter(clasificacion=classification)
        if identifier and request.user.is_staff:
            queryset = queryset.filter(Q(co_id=identifier) | Q(linea=identifier))
        for item in queryset.order_by("id_resultado").iterator(chunk_size=500):
            row = _result_display(item, request.user.is_staff)
            operations.add(row["operation"])
            campaigns.add(row["campaign"])
            if operation and row["operation"] != operation:
                continue
            if campaign and row["campaign"] != campaign:
                continue
            result_rows.append(row)
    page = Paginator(result_rows, 50).get_page(request.GET.get("pagina"))
    today = date.today()
    run_form = ValidationRunForm(
        initial={"desde": today - timedelta(days=1), "hasta": today - timedelta(days=1)},
        max_days=settings.VALIDATION_MAX_DAYS,
    )
    return render(
        request,
        "portal/validaciones.html",
        {
            "title": "Validaciones",
            "executions": [_execution_context(item) for item in executions],
            "selected": selected,
            "page": page,
            "run_form": run_form,
            "classification": classification,
            "operation": operation,
            "campaign": campaign,
            "identifier": identifier,
            "operations": sorted(operations),
            "campaigns": sorted(campaigns),
        },
    )


@administrator_required
def validation_start(request):
    if request.method != "POST":
        return redirect("validaciones")
    form = ValidationRunForm(request.POST, max_days=settings.VALIDATION_MAX_DAYS)
    if not form.is_valid():
        messages.error(request, "Revise las fechas indicadas para la ejecución.")
        return redirect("validaciones")
    try:
        execution = create_execution(
            form.cleaned_data["desde"],
            form.cleaned_data["hasta"],
            "MANUAL",
            user=request.user,
            ip_address=_client_ip(request),
        )
    except DuplicateExecution as error:
        messages.error(request, str(error))
        return redirect("validaciones")
    start_background_execution(execution.pk)
    messages.success(request, f"La ejecución #{execution.pk} comenzó en segundo plano.")
    return redirect(f"/validaciones/?ejecucion={execution.pk}")


@login_required
def validation_detail(request, result_id):
    item = get_object_or_404(
        ValidationStoredResult.objects.select_related("ejecucion", "version"),
        pk=result_id,
    )
    row = _result_display(item, request.user.is_staff)
    return render(
        request,
        "portal/validation_detail.html",
        {"title": f"Resultado #{item.pk}", "row": row},
    )


@administrator_required
def validation_export(request, execution_id):
    execution = get_object_or_404(ValidationExecution, pk=execution_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="validacion_{execution.pk}_{execution.fecha_desde}_{execution.fecha_hasta}.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            "ID_RESULTADO", "CO_ID", "LINEA", "OPERACION", "CAMPANA",
            "PLAN", "DESCUENTO_ESPERADO", "DESCUENTO_APLICADO", "DIFERENCIA",
            "RESULTADO", "CODIGO_MOTIVO", "DETALLE",
        ]
    )
    queryset = ValidationStoredResult.objects.filter(ejecucion=execution).select_related("version")
    for item in queryset.order_by("id_resultado").iterator(chunk_size=500):
        row = _result_display(item, True)
        writer.writerow(
            [
                item.pk, item.co_id, item.linea, row["operation"], row["campaign"],
                item.plan_monto, item.descuento_esperado, item.descuento_aplicado,
                item.diferencia, item.clasificacion, item.codigo_motivo,
                item.descripcion_motivo,
            ]
        )
    return response
