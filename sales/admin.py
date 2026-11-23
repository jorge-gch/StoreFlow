from django.contrib import admin
from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_price', 'subtotal')
    can_delete = False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'user', 'date', 'total', 'payment_method', 'status')
    list_filter = ('status', 'payment_method', 'date')
    search_fields = ('invoice_number', 'customer__name', 'user__username')
    readonly_fields = ('invoice_number', 'date', 'subtotal', 'total', 'cancelled_at')
    inlines = (SaleItemInline,)
