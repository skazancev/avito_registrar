from django.contrib import admin

from .models import AvitoUser


@admin.register(AvitoUser)
class AvitoUserAdmin(admin.ModelAdmin):
    list_display = ['login', 'email', 'password', 'phone', 'created_at']
    search_fields = ['login', 'email', 'phone']
