"""
URLs de la aplicación ``enviropro``.

Mapea las páginas mínimas del enunciado (apartado C2):

* ``/`` — Inicio.
* ``/dashboard/`` — Resumen con indicadores y gráficos.
* ``/humedad/`` — Listado y gráfico de humedad.
* ``/temperatura/`` — Listado y gráfico de temperatura.
* ``/energia/`` — Batería y panel solar.
* ``/alertas/`` — Listado de alertas (con detalle y gestión).
* ``/recomendaciones/`` — CRUD de recomendaciones.
* ``/importacion/`` — Carga manual de un CSV.
* ``/acerca/`` — Información del proyecto.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("humedad/", views.humedad, name="humedad"),
    path("temperatura/", views.temperatura, name="temperatura"),
    path("energia/", views.energia, name="energia"),

    # Alertas
    path("alertas/", views.alertas_listado, name="alertas_listado"),
    path("alertas/<int:pk>/", views.alerta_detalle, name="alerta_detalle"),
    path("alertas/<int:pk>/revisar/", views.alerta_marcar_revisada,
         name="alerta_revisar"),

    # CRUD recomendaciones
    path("recomendaciones/", views.recomendacion_listado,
         name="recomendacion_listado"),
    path("recomendaciones/nueva/", views.recomendacion_crear,
         name="recomendacion_crear"),
    path("recomendaciones/<int:pk>/", views.recomendacion_detalle,
         name="recomendacion_detalle"),
    path("recomendaciones/<int:pk>/editar/", views.recomendacion_editar,
         name="recomendacion_editar"),
    path("recomendaciones/<int:pk>/eliminar/", views.recomendacion_eliminar,
         name="recomendacion_eliminar"),

    # Observaciones sobre lecturas
    path("lecturas/<int:pk>/observacion/", views.lectura_observacion,
         name="lectura_observacion"),

    # Importación
    path("importacion/", views.importacion, name="importacion"),

    # Acerca del proyecto
    path("acerca/", views.acerca, name="acerca"),
]
