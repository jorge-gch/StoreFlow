from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_dashboard, name='dashboard'),
    path('exportar/excel/', views.export_report_excel, name='export_excel'),
    path('exportar/pdf/', views.export_report_pdf, name='export_pdf'),
]
