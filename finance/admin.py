from django.contrib import admin
from .models import FinancialCategory, FinancialMovement


@admin.register(FinancialCategory)
class FinancialCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'movement_type', 'is_system', 'is_active', 'created_at')
    list_filter = ('movement_type', 'is_system', 'is_active')
    search_fields = ('name',)


@admin.register(FinancialMovement)
class FinancialMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'movement_type', 'category', 'description', 'amount', 'payment_method', 'user', 'is_cancelled')
    list_filter = ('movement_type', 'payment_method', 'is_cancelled', 'category')
    search_fields = ('description', 'notes', 'user__username')
    readonly_fields = ('created_at',)
