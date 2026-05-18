"""Panel /admin/ de Django para enviropro."""
from django.contrib import admin
from .models import Alert, EnviroProRecord, Recommendation


@admin.register(EnviroProRecord)
class EnviroProRecordAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "humedad_media", "temp_suelo_media", "bateria_v", "panel_solar_v")
    list_filter = ("fecha_hora",)
    search_fields = ("observaciones",)
    date_hierarchy = "fecha_hora"
    ordering = ("-fecha_hora",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "tipo", "nivel", "variable", "revisada")
    list_filter = ("tipo", "nivel", "revisada")
    search_fields = ("descripcion", "variable")
    date_hierarchy = "fecha_hora"
    list_editable = ("revisada",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("titulo", "prioridad", "estado", "creada_por", "creada_en")
    list_filter = ("prioridad", "estado")
    search_fields = ("titulo", "descripcion")
