"""Vistas de la aplicacion enviropro."""

from __future__ import annotations
import json
import sys
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ImportarForm, ObservacionForm, RecomendacionForm, RegistroForm
from .models import Alert, EnviroProRecord, Recommendation


def _cargar_resumen_kpis():
    ruta = settings.ANALYSIS_OUTPUTS / "indicadores_resumen.json"
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _kpis_desde_db():
    qs = EnviroProRecord.objects.all()
    if not qs.exists():
        return {"total_registros": 0}
    agg = qs.aggregate(
        humedad=Avg("humedad_media"), hum_min=Min("humedad_min"), hum_max=Max("humedad_max"),
        temp=Avg("temp_suelo_media"), t_min=Min("temp_suelo_min"), t_max=Max("temp_suelo_max"),
        bat=Avg("bateria_v"), panel=Avg("panel_solar_v"),
        primera=Min("fecha_hora"), ultima=Max("fecha_hora"),
    )
    return {
        "total_registros": qs.count(),
        "humedad_media_global": agg["humedad"],
        "humedad_min_global": agg["hum_min"],
        "humedad_max_global": agg["hum_max"],
        "temp_media_global": agg["temp"],
        "temp_min_global": agg["t_min"],
        "temp_max_global": agg["t_max"],
        "bateria_media_v": agg["bat"],
        "panel_solar_media_v": agg["panel"],
        "fecha_primera_lectura": agg["primera"].isoformat() if agg["primera"] else None,
        "fecha_ultima_lectura": agg["ultima"].isoformat() if agg["ultima"] else None,
    }


def _listado_graficas():
    if not settings.ANALYSIS_GRAPHS.exists():
        return []
    return sorted(p.name for p in settings.ANALYSIS_GRAPHS.glob("*.png"))


def inicio(request):
    return render(request, "enviropro/inicio.html")


def acerca(request):
    return render(request, "enviropro/acerca.html")


def dashboard(request):
    kpis = _cargar_resumen_kpis() or _kpis_desde_db()
    alertas_por_nivel = {
        nivel: Alert.objects.filter(nivel=nivel).count()
        for nivel in ("info", "aviso", "critico")
    }
    return render(request, "enviropro/dashboard.html", {
        "kpis": kpis,
        "alertas_por_nivel": alertas_por_nivel,
        "alertas_recientes": Alert.objects.order_by("-fecha_hora")[:8],
        "ultima_recomendacion": Recommendation.objects.order_by("-creada_en").first(),
        "graficas": _listado_graficas()[:6],
    })


def humedad(request):
    lecturas = EnviroProRecord.objects.exclude(humedad_media__isnull=True).order_by("-fecha_hora")[:200]
    return render(request, "enviropro/humedad.html", {
        "lecturas": lecturas,
        "graficas": ["01_humedad_temporal.png", "05_humedad_por_sensor_box.png", "07_humedad_diaria.png"],
    })


def temperatura(request):
    lecturas = EnviroProRecord.objects.exclude(temp_suelo_media__isnull=True).order_by("-fecha_hora")[:200]
    return render(request, "enviropro/temperatura.html", {
        "lecturas": lecturas,
        "graficas": ["02_temperatura_temporal.png", "06_temp_por_sensor_box.png", "08_temperatura_diaria.png"],
    })


def energia(request):
    lecturas = EnviroProRecord.objects.exclude(bateria_v__isnull=True).order_by("-fecha_hora")[:200]
    return render(request, "enviropro/energia.html", {
        "lecturas": lecturas,
        "graficas": ["03_bateria_temporal.png", "04_panel_solar_temporal.png"],
    })


def alertas_listado(request):
    tipo = request.GET.get("tipo")
    nivel = request.GET.get("nivel")
    revisada = request.GET.get("revisada")
    qs = Alert.objects.all()
    if tipo: qs = qs.filter(tipo=tipo)
    if nivel: qs = qs.filter(nivel=nivel)
    if revisada in ("0", "1"): qs = qs.filter(revisada=bool(int(revisada)))
    qs = qs.order_by("-fecha_hora")[:500]
    tipos = Alert.objects.values_list("tipo", flat=True).distinct().order_by("tipo")
    return render(request, "enviropro/alertas.html", {
        "alertas": qs, "tipos": list(tipos),
        "filtro_tipo": tipo or "", "filtro_nivel": nivel or "",
        "filtro_revisada": revisada or "",
    })


def alerta_detalle(request, pk):
    alerta = get_object_or_404(Alert, pk=pk)
    return render(request, "enviropro/alerta_detalle.html", {"alerta": alerta})


@login_required
def alerta_marcar_revisada(request, pk):
    alerta = get_object_or_404(Alert, pk=pk)
    alerta.revisada = not alerta.revisada
    alerta.save(update_fields=["revisada"])
    messages.success(request, "Alerta actualizada.")
    return redirect("alerta_detalle", pk=pk)


def recomendacion_listado(request):
    estado = request.GET.get("estado")
    qs = Recommendation.objects.all().order_by("-creada_en")
    if estado in {"pendiente", "revisada", "descartada"}:
        qs = qs.filter(estado=estado)
    return render(request, "enviropro/recomendaciones.html", {
        "recomendaciones": qs, "filtro_estado": estado or "",
    })


def recomendacion_detalle(request, pk):
    rec = get_object_or_404(Recommendation, pk=pk)
    return render(request, "enviropro/recomendacion_detalle.html", {"rec": rec})


@login_required
def recomendacion_crear(request):
    if request.method == "POST":
        form = RecomendacionForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.creada_por = request.user
            rec.save()
            messages.success(request, "Recomendacion creada.")
            return redirect("recomendacion_detalle", pk=rec.pk)
    else:
        form = RecomendacionForm()
    return render(request, "enviropro/recomendacion_form.html",
                  {"form": form, "accion": "Crear nueva recomendacion"})


@login_required
def recomendacion_editar(request, pk):
    rec = get_object_or_404(Recommendation, pk=pk)
    if request.method == "POST":
        form = RecomendacionForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, "Actualizada.")
            return redirect("recomendacion_detalle", pk=rec.pk)
    else:
        form = RecomendacionForm(instance=rec)
    return render(request, "enviropro/recomendacion_form.html",
                  {"form": form, "accion": f"Editar: {rec.titulo}"})


@login_required
def recomendacion_eliminar(request, pk):
    rec = get_object_or_404(Recommendation, pk=pk)
    if request.method == "POST":
        rec.delete()
        messages.success(request, "Eliminada.")
        return redirect("recomendacion_listado")
    return render(request, "enviropro/recomendacion_confirmar_eliminar.html", {"rec": rec})


@login_required
def lectura_observacion(request, pk):
    lectura = get_object_or_404(EnviroProRecord, pk=pk)
    if request.method == "POST":
        form = ObservacionForm(request.POST, instance=lectura)
        if form.is_valid():
            form.save()
            messages.success(request, "Observacion guardada.")
            return redirect("humedad")
    else:
        form = ObservacionForm(instance=lectura)
    return render(request, "enviropro/lectura_observacion.html",
                  {"form": form, "lectura": lectura})


@login_required
def importacion(request):
    ctx = {"form": ImportarForm()}
    if request.method == "POST":
        form = ImportarForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo"]
            settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
            destino = settings.MEDIA_ROOT / archivo.name
            with open(destino, "wb") as f:
                for chunk in archivo.chunks():
                    f.write(chunk)
            modulo_path = (settings.BASE_DIR.parent / "analisis").resolve()
            if str(modulo_path) not in sys.path:
                sys.path.insert(0, str(modulo_path))
            try:
                from analizador import ejecutar_pipeline
                resultado = ejecutar_pipeline(destino)
            except Exception as e:
                messages.error(request, f"Error procesando CSV: {e}")
                return redirect("importacion")
            messages.success(request,
                f"Procesados {len(resultado.df_indicadores)} registros y "
                f"{len(resultado.df_alertas)} alertas. Usa "
                "`python manage.py poblar_bbdd` para persistirlos.")
            return redirect("dashboard")
        ctx["form"] = form
    return render(request, "enviropro/importacion.html", ctx)


def registro(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, f"Bienvenido {usuario.username}.")
            return redirect("dashboard")
    else:
        form = RegistroForm()
    return render(request, "registration/registro.html", {"form": form})
