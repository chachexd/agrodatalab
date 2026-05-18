"""
Formularios de la app ``enviropro``.

Contiene:

* :class:`RegistroForm` — registro público de usuarios (apartado C2,
  página *Usuarios*).
* :class:`RecomendacionForm` — formulario para crear y editar
  recomendaciones (apartado C5, CRUD obligatorio).
* :class:`ObservacionForm` — formulario para añadir observaciones a
  una lectura concreta (apartado C5).
* :class:`ImportarForm` — formulario para subir un CSV de EnviroPro
  desde la web e importarlo a la base de datos (apartado C2).
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import EnviroProRecord, Recommendation


class RegistroForm(UserCreationForm):
    """Formulario de registro de usuarios con email obligatorio."""

    email = forms.EmailField(required=True, label="Correo electrónico")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class RecomendacionForm(forms.ModelForm):
    """Crear o editar recomendaciones manuales."""

    class Meta:
        model = Recommendation
        fields = ("titulo", "descripcion", "prioridad", "estado", "alerta_relacionada")
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }


class ObservacionForm(forms.ModelForm):
    """Permite editar el campo ``observaciones`` de una lectura."""

    class Meta:
        model = EnviroProRecord
        fields = ("observaciones",)
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 4, "placeholder":
                "Notas o contexto sobre esta lectura..."}),
        }


class ImportarForm(forms.Form):
    """Formulario para subir un CSV bruto de EnviroPro a la base de datos."""

    archivo = forms.FileField(
        label="Archivo CSV de EnviroPro",
        help_text="Acepta el formato original con dos filas de cabecera y "
                  "coma decimal, o el consolidado con una sola fila.",
    )
    reemplazar = forms.BooleanField(
        label="Reemplazar lecturas existentes con la misma marca temporal",
        required=False,
        initial=False,
    )
