from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Client(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)

    # Default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    def __str__(self):
        return self.name

class Domain(DomainMixin):
    pass

class Region(models.Model):
    """Canonical registry of valid region codes (public schema, admin-managed)."""
    code = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if not self.code:
            from .regions import generate_region_code
            self.code = generate_region_code(self.name)
        super().save(*args, **kwargs)