from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem, SupplierDebt, SupplierPayment


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_cost', 'subtotal')
    can_delete = False


class SupplierPaymentInline(admin.TabularInline):
    model = SupplierPayment
    extra = 0
    readonly_fields = ('date', 'user', 'amount', 'payment_method', 'reference', 'notes')
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


@admin.register(SupplierDebt)
class SupplierDebtAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'purchase', 'total_amount', 'paid_amount', 'pending_balance', 'is_paid', 'is_cancelled', 'due_date')
    list_filter = ('is_paid', 'is_cancelled', 'due_date')
    search_fields = ('supplier__name', 'purchase__invoice_number')
    inlines = [SupplierPaymentInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ('debt', 'amount', 'payment_method', 'reference', 'date', 'user')
    list_filter = ('payment_method', 'date')
    readonly_fields = ('date',)
