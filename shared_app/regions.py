"""Reusable region lookup and enforcement helpers.

Shared by the request middleware and the tenant API (and any future call sites)
so region rules live in exactly one place. Internally we distinguish
``RegionNotFound`` from ``RegionForbidden`` for clarity and logging, but both are
subclasses of ``RegionError`` and map to HTTP 400 externally.

The ``Region`` registry lives in the public schema, so lookups switch to the
public schema regardless of the current tenant context.
"""

from django.utils.text import slugify
from django_tenants.utils import get_public_schema_name, schema_context


class RegionError(Exception):
    """Base class for region problems; all map to HTTP 400 externally."""


class RegionNotFound(RegionError):
    """The region code is not an active entry in the registry."""


class RegionForbidden(RegionError):
    """An operation targets a region other than the request's region."""


def resolve_region(region_code):
    """Return ``region_code`` if it is an active region, else raise RegionNotFound."""
    from .models import Region

    with schema_context(get_public_schema_name()):
        is_active = Region.objects.filter(code=region_code, is_active=True).exists()
    if not is_active:
        raise RegionNotFound(region_code)
    return region_code


def require_matching_region(request_region, target_region):
    """Raise RegionForbidden if ``target_region`` differs from ``request_region``."""
    if target_region != request_region:
        raise RegionForbidden(target_region)


def generate_region_code(name):
    """Derive a normalized, unique region code from a human-readable name."""
    from .models import Region

    base = slugify(name) or "region"
    code = base
    suffix = 2
    with schema_context(get_public_schema_name()):
        while Region.objects.filter(code=code).exists():
            code = f"{base}-{suffix}"
            suffix += 1
    return code
