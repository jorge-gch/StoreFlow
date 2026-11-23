from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from inventory.models import Product, InventoryMovement
from customers.models import Customer

class Sale(models.Model):
    """
    Modelo maestro de Venta / Factura.
    """
    PAYMENT_CASH = 'cash'
    PAYMENT_TRANSFER = 'transfer'
    PAYMENT_CREDIT = 'credit'
    PAYMENT_PARTIAL = 'partial'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, 'Efectivo'),
        (PAYMENT_TRANSFER, 'Transferencia Bancaria'),
        (PAYMENT_CREDIT, 'Crédito'),
        (PAYMENT_PARTIAL, 'Pago Parcial'),
    ]

    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Completada'),
        (STATUS_CANCELLED, 'Anulada'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, verbose_name='Número de Factura')
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name='Cliente'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name='Vendedor / Usuario'
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Subtotal'
    )
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Descuento'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Total'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_CASH,
        verbose_name='Método de Pago'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
        verbose_name='Estado'
    )
    notes = models.TextField(blank=True, verbose_name='Notas / Observaciones')
    cancellation_reason = models.TextField(blank=True, verbose_name='Motivo de Anulación')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Anulación')

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-date']

    def __str__(self):
        return f"Factura #{self.invoice_number} - ${self.total}"

    @classmethod
    def generate_next_invoice_number(cls):
        """Genera un correlativo secuencial para facturación ej. FAC-000001."""
        last_sale = cls.objects.order_by('-id').first()
        if not last_sale:
            return "FAC-000001"
        try:
            last_num = int(last_sale.invoice_number.split('-')[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = last_sale.id + 1
        return f"FAC-{new_num:06d}"

    @transaction.atomic
    def cancel(self, user, reason=""):
        """
        Anula la venta de forma controlada y revierte las existencias en el inventario.
        """
        if self.status == self.STATUS_CANCELLED:
            raise ValueError("Esta venta ya ha sido anulada previamente.")

        from django.utils import timezone
        self.status = self.STATUS_CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

        # Reingresar productos al inventario mediante Kardex
        for item in self.items.select_related('product').all():
            item.product.adjust_stock(
                quantity=item.quantity,
                movement_type=InventoryMovement.MOVEMENT_IN,
                reference=f"Reversión por anulación Venta #{self.invoice_number}",
                user=user,
                notes=f"Motivo anulación: {reason}"
            )


class SaleItem(models.Model):
    """
    Detalle de cada artículo dentro de una venta.
    """
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Venta'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sale_items',
        verbose_name='Producto'
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad'
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio Unitario'
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Subtotal'
    )

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (${self.subtotal})"

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)
