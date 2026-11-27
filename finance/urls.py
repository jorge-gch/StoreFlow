from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.movement_list, name='movement_list'),
    path('nuevo/', views.movement_create, name='movement_create'),
    path('<int:pk>/anular/', views.movement_cancel, name='movement_cancel'),
    path('categorias/', views.category_list, name='category_list'),
    path('categorias/nueva/', views.category_create, name='category_create'),
    path('categorias/<int:pk>/editar/', views.category_update, name='category_update'),
]
