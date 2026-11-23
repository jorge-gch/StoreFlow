from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from inventory.models import Product, InventoryMovement

class Supplier(models.Model):
    """
    Modelo de Proveedor para compras de mercancía y control de obligaciones comerciales.
    """
    name = models.CharField(max_length=150, verbose_name='Razón Social / Proveedor')
    contact_name = models.CharField(max_length=150, blank=True, verbose_name='Contacto / Asesor')
    tax_id = models.CharField(max_length=50, blank=True, verbose_name='NIT / RUT / Identificación')
    phone = models.CharField(max_length=30, verbose_name='Teléfono de Contacto')
    email = models.EmailField(blank=True, verbose_name='Correo Electrónico')
    address = models.CharField(max_length=255, blank=True, verbose_name='Dirección / Ubicación')
    notes = models.TextField(blank=True, verbose_name='Términos comerciales / Notas')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        if self.tax_id:
            return f"{self.name} (NIT: {self.tax_id})"
        return self.name

    @property
    def total_purchases(self):
        """Total de órdenes de compra realizadas al proveedor."""
        return self.purchases.filter(status=Purchase.STATUS_COMPLETED).count()

    @property
    def total_debt(self):
        """Saldo total pendiente de pago al proveedor."""
        if hasattr(self, 'debts'):
            total = self.debts.filter(is_paid=False).aggregate(models.Sum('pending_balance'))['pending_balance__sum']
            return total or Decimal('0.00')
        return Decimal('0.00')


class Purchase(models.Model):
    """
    Orden / Factura de Compra de mercancía a proveedores.
    """
    PAYMENT_CASH = 'cash'
    PAYMENT_TRANSFER = 'transfer'
    PAYMENT_CREDIT = 'credit'
    PAYMENT_PARTIAL = 'partial'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, 'Efectivo / Contado'),
        (PAYMENT_TRANSFER, 'Transferencia Bancaria'),
        (PAYMENT_CREDIT, 'Crédito Proveedor'),
        (PAYMENT_PARTIAL, 'Pago Parcial'),
    ]

    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Recibida / Completada'),
        (STATUS_CANCELLED, 'Anulada'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, verbose_name='Número de Factura Compra')
    supplier_invoice = models.CharField(max_length=50, blank=True, verbose_name='Factura del Proveedor (Opcional)')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name='Proveedor'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name='Usuario Responsable'
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Subtotal'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Total de la Compra'
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
    notes = models.TextField(blank=True, verbose_name='Observaciones')
    cancellation_reason = models.TextField(blank=True, verbose_name='Motivo de Anulación')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Anulación')

    class Meta:
        verbose_name = 'Compra de Mercancía'
        verbose_name_plural = 'Compras de Mercancía'
        ordering = ['-date']

    def __str__(self):
        return f"Compra #{self.invoice_number} - {self.supplier.name} (${self.total})"

    @classmethod
    def generate_next_invoice_number(cls):
        """Genera un correlativo secuencial para compras ej. COM-000001."""
        last_purchase = cls.objects.order_by('-id').first()
        if not last_purchase:
            return "COM-000001"
        try:
            last_num = int(last_purchase.invoice_number.split('-')[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = last_purchase.id + 1
        return f"COM-{new_num:06d}"

    @transaction.atomic
    def cancel(self, user, reason=""):
        """
        Anula la compra y descuenta del inventario las unidades ingresadas.
        """
        if self.status == self.STATUS_CANCELLED:
            raise ValueError("Esta compra ya se encuentra anulada.")

        # Verificar si hay suficiente stock de cada producto para revertir la compra
        for item in self.items.select_related('product').all():
            if item.product.stock < item.quantity:
                raise ValueError(
                    f"No se puede anular la compra. El producto '{item.product.name}' ya ha sido vendido y solo cuenta con {item.product.stock} unidades en stock (se requieren {item.quantity})."
                )

        from django.utils import timezone
        self.status = self.STATUS_CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

        # Descontar del inventario con Kardex
        for item in self.items.select_related('product').all():
            item.product.adjust_stock(
                quantity=item.quantity,
                movement_type=InventoryMovement.MOVEMENT_OUT,
                reference=f"Reversión por anulación Compra #{self.invoice_number}",
                user=user,
                notes=f"Proveedor: {self.supplier.name}. Motivo: {reason}"
            )


class PurchaseItem(models.Model):
    """
    Detalle de cada producto adquirido en una compra.
    """
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Compra'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='purchase_items',
        verbose_name='Producto'
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad Comprada'
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio de Compra Unitario'
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Subtotal'
    )

    class Meta:
        verbose_name = 'Detalle de Compra'
        verbose_name_plural = 'Detalles de Compra'

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (${self.subtotal})"

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_cost * self.quantity
        super().save(*args, **kwargs)
