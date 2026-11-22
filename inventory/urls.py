from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Productos
    path('productos/', views.product_list, name='product_list'),
    path('productos/nuevo/', views.product_create, name='product_create'),
    path('productos/<int:pk>/', views.product_detail, name='product_detail'),
    path('productos/<int:pk>/editar/', views.product_update, name='product_update'),
    path('productos/<int:pk>/toggle/', views.product_toggle_active, name='product_toggle_active'),
    path('productos/<int:pk>/ajustar-stock/', views.product_adjust_stock, name='product_adjust_stock'),

    # Kardex / Movimientos
    path('movimientos/', views.movement_list, name='movement_list'),

    # Categorías
    path('categorias/', views.category_list, name='category_list'),
    path('categorias/<int:pk>/editar/', views.category_update, name='category_update'),
]
