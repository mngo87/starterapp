from django.contrib import admin
from .models import Member

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'region_id', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'phone', 'region_id')
