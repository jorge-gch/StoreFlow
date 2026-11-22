from django.contrib import admin
from .models import Category, Product, InventoryMovement

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'total_products', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'category', 'cost_price', 'sale_price', 'stock', 'min_stock', 'is_low_stock', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('sku', 'name')
    list_editable = ('sale_price', 'cost_price', 'min_stock')

@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'reference', 'user', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__name', 'product__sku', 'reference')
    readonly_fields = ('product', 'movement_type', 'quantity', 'previous_stock', 'new_stock', 'reference', 'user', 'created_at')
