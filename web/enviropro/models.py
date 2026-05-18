"""
Modelos de la aplicacion enviropro.

Materializan los apartados C4 y C5 del enunciado:
  - EnviroProRecord: lectura horaria consolidada.
  - Alert: alerta del sistema con nivel, tipo y variable.
  - Recommendation: recomendaciones manuales con CRUD completo.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse


class EnviroProRecord(models.Model):
    fecha_hora = models.DateTimeField("Fecha y hora", unique=True, db_index=True)
    humedad_media = models.FloatField("Humedad media (%)", null=True, blank=True)
    humedad_min = models.FloatField("Humedad min (%)", null=True, blank=True)
    humedad_max = models.FloatField("Humedad max (%)", null=True, blank=True)
    temp_suelo_media = models.FloatField("Temperatura media (C)", null=True, blank=True)
    temp_suelo_max = models.FloatField("Temperatura max (C)", null=True, blank=True)
    temp_suelo_min = models.FloatField("Temperatura min (C)", null=True, blank=True)
    bateria_v = models.FloatField("Bateria (V)", null=True, blank=True)
    panel_solar_v = models.FloatField("Panel solar (V)", null=True, blank=True)
    observaciones = models.TextField("Observaciones", blank=True, default="")

    class Meta:
        verbose_name = "Lectura EnviroPro"
        verbose_name_plural = "Lecturas EnviroPro"
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"EnviroPro @ {self.fecha_hora:%Y-%m-%d %H:%M}"


class Alert(models.Model):
    class Nivel(models.TextChoices):
        INFO = "info", "Informativa"
        AVISO = "aviso", "Aviso"
        CRITICO = "critico", "Critica"

    fecha_hora = models.DateTimeField("Fecha y hora", db_index=True)
    tipo = models.CharField("Tipo", max_length=64, db_index=True)
    nivel = models.CharField("Nivel", max_length=10, choices=Nivel.choices, default=Nivel.INFO)
    variable = models.CharField("Variable", max_length=64)
    descripcion = models.TextField("Descripcion")
    recomendacion = models.TextField("Recomendacion", blank=True, default="")
    revisada = models.BooleanField("Revisada", default=False)

    class Meta:
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        ordering = ["-fecha_hora", "-nivel"]

    def __str__(self):
        return f"[{self.nivel}] {self.tipo} @ {self.fecha_hora:%Y-%m-%d %H:%M}"

    def get_absolute_url(self):
        return reverse("alerta_detalle", args=[self.pk])


class Recommendation(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        REVISADA = "revisada", "Revisada"
        DESCARTADA = "descartada", "Descartada"

    class Prioridad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"

    titulo = models.CharField("Titulo", max_length=200)
    descripcion = models.TextField("Descripcion")
    alerta_relacionada = models.ForeignKey(
        Alert, verbose_name="Alerta relacionada",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recomendaciones",
    )
    prioridad = models.CharField("Prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField("Estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Creada por",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recomendaciones_creadas",
    )
    creada_en = models.DateTimeField("Creada en", auto_now_add=True)
    actualizada_en = models.DateTimeField("Actualizada en", auto_now=True)

    class Meta:
        verbose_name = "Recomendacion"
        verbose_name_plural = "Recomendaciones"
        ordering = ["-creada_en"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        return reverse("recomendacion_detalle", args=[self.pk])
