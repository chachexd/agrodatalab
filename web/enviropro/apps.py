"""Configuración de la app Django enviropro."""

from django.apps import AppConfig


class EnviroproConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enviropro"
    verbose_name = "EnviroPro - AgroDataLab Web"
