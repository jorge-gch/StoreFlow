from decimal import Decimal
from django.db import models

class Customer(models.Model):
    """
    Modelo de Cliente para control de ventas, crédito y cobranzas.
    """
    name = models.CharField(max_length=150, verbose_name='Nombre Completo')
    document_id = models.CharField(max_length=50, blank=True, verbose_name='Documento / Identificación')
    phone = models.CharField(max_length=30, verbose_name='Teléfono / WhatsApp')
    email = models.EmailField(blank=True, verbose_name='Correo Electrónico')
    address = models.CharField(max_length=255, blank=True, verbose_name='Dirección')
    notes = models.TextField(blank=True, verbose_name='Observaciones / Referencias')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['name']

    def __str__(self):
        if self.document_id:
            return f"{self.name} ({self.document_id})"
        return self.name

    @property
    def total_purchases(self):
        """Total de ventas completadas acumuladas por el cliente."""
        if hasattr(self, 'sales'):
            return self.sales.filter(status='completed').count()
        return 0

    @property
    def total_debt(self):
        """Saldo total pendiente por cobrar al cliente."""
        if hasattr(self, 'debts'):
            total = self.debts.filter(is_paid=False).aggregate(models.Sum('pending_balance'))['pending_balance__sum']
            return total or Decimal('0.00')
        return Decimal('0.00')
