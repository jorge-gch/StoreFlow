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

    # Cuentas por Pagar (Fase 7)
    path('cuentas-pagar/', views.debt_list, name='debt_list'),
    path('cuentas-pagar/<int:pk>/', views.debt_detail, name='debt_detail'),
    path('cuentas-pagar/<int:pk>/pagar/', views.debt_register_payment, name='debt_register_payment'),
]
