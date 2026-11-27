from django.contrib import admin
from .models import Customer, CustomerDebt, CustomerPayment


class CustomerPaymentInline(admin.TabularInline):
    model = CustomerPayment
    extra = 0
    readonly_fields = ('date', 'user', 'amount', 'payment_method', 'notes')
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_id', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'document_id', 'phone', 'email')


@admin.register(CustomerDebt)
class CustomerDebtAdmin(admin.ModelAdmin):
    list_display = ('customer', 'sale', 'total_amount', 'paid_amount', 'pending_balance', 'is_paid', 'is_cancelled', 'due_date')
    list_filter = ('is_paid', 'is_cancelled', 'due_date')
    search_fields = ('customer__name', 'sale__invoice_number')
    inlines = [CustomerPaymentInline]


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ('debt', 'amount', 'payment_method', 'date', 'user')
    list_filter = ('payment_method', 'date')
    readonly_fields = ('date',)
