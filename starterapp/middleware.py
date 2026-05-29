"""Region-aware request middleware.

Runs immediately after ``TenantSubfolderMiddleware`` so the tenant is already
resolved. For routes that capture a ``region_id`` URL kwarg (i.e.
``/client/<domain>/region/<region_id>/api/...``) it validates the code against
the active ``Region`` registry and exposes it as ``request.region_id``. Any
region problem maps to HTTP 400. Routes without a ``region_id`` kwarg (e.g. the
tenant admin) pass through untouched.
"""

from django.http import HttpResponse

from shared_app.regions import RegionError, resolve_region


class RegionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        region_code = view_kwargs.get("region_id")
        if region_code is None:
            return None
        try:
            request.region_id = resolve_region(region_code)
        except RegionError:
            return HttpResponse(status=400)
        return None
