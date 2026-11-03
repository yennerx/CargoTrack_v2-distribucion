from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import CatalogEntry, CatalogType, SystemConfiguration


@login_required
@require_GET
def dashboard(request):
    if not request.user.has_perm("catalogs.view_catalogentry"):
        raise PermissionDenied

    groups = []
    for catalog_type, label in CatalogType.choices:
        entries = CatalogEntry.objects.filter(catalog_type=catalog_type)
        groups.append(
            {
                "label": label,
                "entries": entries,
                "active_count": entries.filter(is_active=True).count(),
            }
        )
    return render(
        request,
        "catalogs/dashboard.html",
        {
            "catalog_groups": groups,
            "configurations": SystemConfiguration.objects.filter(is_active=True),
        },
    )
