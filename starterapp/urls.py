from django.contrib import admin
from django.urls import path
from tenant_app.api import api as tenant_api
from django.views import defaults as default_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('region/<str:region_id>/api/', tenant_api.urls),
]

# Define error handlers
handler400 = default_views.bad_request
handler403 = default_views.permission_denied
handler404 = default_views.page_not_found
handler500 = default_views.server_error 