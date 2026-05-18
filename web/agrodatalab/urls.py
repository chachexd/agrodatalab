"""URLs raiz de AgroDataLab Web."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path

from enviropro import views as enviropro_views


def servir_grafica(request, nombre):
    ruta = settings.ANALYSIS_GRAPHS / nombre
    if not ruta.exists() or ruta.suffix.lower() != ".png":
        raise Http404("Grafica no encontrada")
    return FileResponse(open(ruta, "rb"), content_type="image/png")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("cuentas/registro/", enviropro_views.registro, name="registro"),
    path("graficas/<str:nombre>", servir_grafica, name="grafica"),
    path("", include("enviropro.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
