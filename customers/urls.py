from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('nuevo/', views.customer_create, name='customer_create'),
    path('cuentas-cobrar/', views.debt_list, name='debt_list'),
    path('cuentas-cobrar/<int:pk>/', views.debt_detail, name='debt_detail'),
    path('cuentas-cobrar/<int:pk>/abonar/', views.debt_register_payment, name='debt_register_payment'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/editar/', views.customer_update, name='customer_update'),
    path('<int:pk>/toggle/', views.customer_toggle_active, name='customer_toggle_active'),
]
