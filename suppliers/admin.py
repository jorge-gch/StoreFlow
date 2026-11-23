from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_cost', 'subtotal')
    can_delete = False

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'tax_id', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'contact_name', 'tax_id', 'phone', 'email')

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier', 'user', 'date', 'total', 'payment_method', 'status')
    list_filter = ('status', 'payment_method', 'date')
    search_fields = ('invoice_number', 'supplier__name', 'supplier_invoice')
    readonly_fields = ('invoice_number', 'date', 'subtotal', 'total', 'cancelled_at')
    inlines = (PurchaseItemInline,)
