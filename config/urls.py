"""
URL Configuration for StoreFlow project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('inventario/', include('inventory.urls')),
    path('clientes/', include('customers.urls')),
    path('proveedores/', include('suppliers.urls')),
    path('ventas/', include('sales.urls')),
    path('finanzas/', include('finance.urls')),
    path('reportes/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
