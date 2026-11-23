from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Directorio de Proveedores
    path('', views.supplier_list, name='supplier_list'),
    path('nuevo/', views.supplier_create, name='supplier_create'),
    path('<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('<int:pk>/editar/', views.supplier_update, name='supplier_update'),
    path('<int:pk>/toggle/', views.supplier_toggle_active, name='supplier_toggle_active'),

    # Órdenes de Compra (Fase 6)
    path('compras/', views.purchase_list, name='purchase_list'),
    path('compras/nueva/', views.purchase_create, name='purchase_create'),
    path('compras/<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('compras/<int:pk>/anular/', views.purchase_cancel, name='purchase_cancel'),
]
