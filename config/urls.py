from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("configuracion/", include("apps.catalogs.urls")),
    path("clientes/", include("apps.customers.urls")),
    path("transportistas/", include("apps.carriers.urls")),
    path("ordenes/", include("apps.orders.urls")),
    path("documentos/", include("apps.documents.urls")),
    path("incidencias/", include("apps.incidents.urls")),
    path("finanzas/", include("apps.finance.urls")),
    path("auditoria/", include("apps.audit.urls")),
    path("reportes/", include("apps.reports.urls")),
    path("", include("apps.core.urls")),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.forbidden"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
