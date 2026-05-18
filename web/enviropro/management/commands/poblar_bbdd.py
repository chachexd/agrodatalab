"""
Management command ``poblar_bbdd``.

Lee los CSV generados por ``analisis/main.py``
(``enviropro_limpio.csv`` y ``alertas.csv``) y los inserta en la base
de datos de la aplicación Django, generando registros para
:class:`enviropro.models.EnviroProRecord` y :class:`Alert`.

Uso::

    python manage.py poblar_bbdd
    python manage.py poblar_bbdd --max 5000     # importar solo 5000 lecturas
    python manage.py poblar_bbdd --reiniciar    # vaciar tablas antes
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime

from enviropro.models import Alert, EnviroProRecord, Recommendation


class Command(BaseCommand):
    help = "Importa CSVs procesados a EnviroProRecord y Alert."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--max", type=int, default=None,
            help="Limita el número de lecturas a importar (útil en desarrollo).",
        )
        parser.add_argument(
            "--reiniciar", action="store_true",
            help="Vacía las tablas EnviroProRecord, Alert y Recommendation antes de importar.",
        )
        parser.add_argument(
            "--solo-resumen", action="store_true",
            help="Importa solo 1 lectura por día para acelerar la demo.",
        )

    def handle(self, *args, **options):  # noqa: D401
        ruta_lecturas = settings.ANALYSIS_OUTPUTS / "enviropro_limpio.csv"
        ruta_alertas = settings.ANALYSIS_OUTPUTS / "alertas.csv"
        if not ruta_lecturas.exists():
            self.stderr.write(
                f"No encuentro {ruta_lecturas}. Ejecuta primero analisis/main.py."
            )
            return

        if options["reiniciar"]:
            self.stdout.write("Reiniciando tablas...")
            Recommendation.objects.all().delete()
            Alert.objects.all().delete()
            EnviroProRecord.objects.all().delete()

        self.stdout.write(f"Importando lecturas desde {ruta_lecturas}")
        creados = 0
        ultimo_dia = None
        objetos = []
        with open(ruta_lecturas, "r", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            for fila in lector:
                if options["max"] and creados >= options["max"]:
                    break
                fecha = parse_datetime(fila["fecha_hora"])
                if fecha is None:
                    continue
                # Si se pidió "solo-resumen" nos quedamos con una lectura por día.
                if options["solo_resumen"]:
                    dia = fecha.date()
                    if dia == ultimo_dia:
                        continue
                    ultimo_dia = dia

                def _f(col: str):
                    val = fila.get(col)
                    if val in (None, "", "nan"):
                        return None
                    try:
                        return float(val)
                    except ValueError:
                        return None

                objetos.append(EnviroProRecord(
                    fecha_hora=fecha,
                    humedad_media=_f("humedad_media_global"),
                    humedad_min=_f("humedad_min_global"),
                    humedad_max=_f("humedad_max_global"),
                    temp_suelo_media=_f("temp_media_global"),
                    temp_suelo_max=_f("temp_max_global"),
                    temp_suelo_min=_f("temp_min_global"),
                    bateria_v=_f("bateria_v"),
                    panel_solar_v=_f("panel_solar_v"),
                ))
                creados += 1
                if len(objetos) >= 1000:
                    EnviroProRecord.objects.bulk_create(objetos, ignore_conflicts=True)
                    objetos.clear()
        if objetos:
            EnviroProRecord.objects.bulk_create(objetos, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(
            f"Lecturas insertadas: {creados}"
        ))

        # Alertas
        if not ruta_alertas.exists():
            self.stdout.write("No hay archivo de alertas; salto.")
            return

        self.stdout.write(f"Importando alertas desde {ruta_alertas}")
        nivel_valido = {"info", "aviso", "critico"}
        alertas_obj = []
        with open(ruta_alertas, "r", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                fecha = parse_datetime(fila["fecha_hora"])
                if fecha is None:
                    continue
                nivel = fila.get("nivel", "info")
                if nivel not in nivel_valido:
                    nivel = "info"
                alertas_obj.append(Alert(
                    fecha_hora=fecha,
                    tipo=fila["tipo"][:64],
                    nivel=nivel,
                    variable=fila["variable"][:64],
                    descripcion=fila["descripcion"],
                    recomendacion=fila.get("recomendacion", ""),
                ))
                if len(alertas_obj) >= 1000:
                    Alert.objects.bulk_create(alertas_obj)
                    alertas_obj.clear()
        if alertas_obj:
            Alert.objects.bulk_create(alertas_obj)
        total_alertas = Alert.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Alertas insertadas en total: {total_alertas}"
        ))

        # Crear una recomendación de ejemplo si no hay ninguna.
        if not Recommendation.objects.exists():
            primera = Alert.objects.filter(nivel="critico").first() or Alert.objects.first()
            if primera:
                Recommendation.objects.create(
                    titulo=f"Revisión asociada a {primera.tipo}",
                    descripcion=(
                        "Recomendación generada automáticamente al importar la "
                        "base de datos. Revisar la alerta correspondiente y "
                        "validar con el equipo agrario."
                    ),
                    alerta_relacionada=primera,
                    prioridad="media",
                )
                self.stdout.write("Recomendación de ejemplo creada.")
