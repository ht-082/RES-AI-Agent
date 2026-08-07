from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['name', 'email', 'department', 'role', 'date_joined']
    search_fields = ['name', 'email']
    list_filter = ['role', 'department']
    ordering = ['-date_joined']

    # AbstractUser 기본 fieldset 확장
    fieldsets = BaseUserAdmin.fieldsets + (
        ('추가 정보', {'fields': ('name', 'department', 'role')}),
    )
