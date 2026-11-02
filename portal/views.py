from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .campaign_repository import load_configured_campaigns
from .source_csv import CampaignSourceUnavailable


def campaign_display(row):
    row = dict(row)
    raw_percentage = row.get("PORCENTAJE", "")
    if raw_percentage:
        try:
            percentage = Decimal(raw_percentage.replace(",", ".")) * 100
            text = format(percentage, "f")
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            row["BENEFICIO_DISPLAY"] = f"{text}%"
        except InvalidOperation:
            row["BENEFICIO_DISPLAY"] = "Valor porcentual inválido"
    else:
        row["BENEFICIO_DISPLAY"] = row.get("DESCRIPCION") or "Pendiente de parametrizar"
    return row


@login_required
def inicio(request):
    try:
        campaigns = load_configured_campaigns(settings)
        active_count = sum(row.get("ESTADO") == "A" for row in campaigns)
        source_state = "Disponible"
    except CampaignSourceUnavailable:
        active_count = None
        source_state = "Pendiente de configurar"
    return render(
        request,
        "portal/inicio.html",
        {
            "title": "Inicio",
            "active_count": active_count,
            "source_state": source_state,
        },
    )


@login_required
def campanas(request):
    query = request.GET.get("q", "").strip().casefold()
    operation = request.GET.get("operacion", "").strip()
    status = request.GET.get("estado", "").strip()
    error = None
    rows = []
    try:
        rows = [campaign_display(row) for row in load_configured_campaigns(settings)]
        if query:
            rows = [
                row for row in rows
                if query in f"{row.get('ID_CAMPANA', '')} {row.get('NOMBRE_CAMPANA', '')} {row.get('COD_PLAN', '')}".casefold()
            ]
        if operation:
            rows = [row for row in rows if row.get("ESCENARIO") == operation]
        if status:
            rows = [row for row in rows if row.get("ESTADO") == status]
    except CampaignSourceUnavailable as exc:
        error = str(exc)
    return render(
        request,
        "portal/campanas.html",
        {
            "title": "Campañas",
            "rows": rows,
            "error": error,
            "q": request.GET.get("q", ""),
            "operation": operation,
            "status": status,
        },
    )


@login_required
def validaciones(request):
    return render(
        request,
        "portal/validaciones.html",
        {"title": "Validaciones"},
    )
