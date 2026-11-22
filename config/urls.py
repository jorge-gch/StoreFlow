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
    # En las siguientes fases se irán vinculando las URLs de:
    # inventory, sales, customers, finance, suppliers, reports
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
