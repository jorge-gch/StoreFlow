from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
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
        total = self.debts.filter(is_paid=False, is_cancelled=False).aggregate(
            models.Sum('pending_balance')
        )['pending_balance__sum']
        return total or Decimal('0.00')


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

        # Anular deuda asociada si existe
        if hasattr(self, 'debt'):
            self.debt.is_cancelled = True
            self.debt.save(update_fields=['is_cancelled', 'updated_at'])
            for pay in self.debt.payments.all():
                if hasattr(pay, 'financial_movement'):
                    pay.financial_movement.is_cancelled = True
                    pay.financial_movement.save(update_fields=['is_cancelled'])

        # Anular movimiento financiero asociado si existe (compra de contado)
        if hasattr(self, 'financial_movement'):
            self.financial_movement.is_cancelled = True
            self.financial_movement.save(update_fields=['is_cancelled'])


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


class SupplierDebt(models.Model):
    """
    Cuenta por pagar asociada a una compra a crédito o pago parcial con un proveedor.
    """
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='debts',
        verbose_name='Proveedor'
    )
    purchase = models.OneToOneField(
        Purchase,
        on_delete=models.CASCADE,
        related_name='debt',
        verbose_name='Compra Asociada'
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Total'
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Total Pagado'
    )
    pending_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Saldo Pendiente'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Fecha de Vencimiento')
    is_paid = models.BooleanField(default=False, verbose_name='Saldada')
    is_cancelled = models.BooleanField(default=False, verbose_name='Anulada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Cuenta por Pagar'
        verbose_name_plural = 'Cuentas por Pagar'
        ordering = ['-created_at']

    def __str__(self):
        return f"Por Pagar #{self.purchase.invoice_number} - {self.supplier.name} (Saldo: ${self.pending_balance})"

    @property
    def is_overdue(self):
        if self.is_paid or self.is_cancelled or not self.due_date:
            return False
        return self.due_date < timezone.localdate()

    @transaction.atomic
    def register_payment(self, amount, payment_method, user, reference="", notes=""):
        """
        Registra un abono / pago realizado al proveedor de forma atómica.
        """
        if self.is_cancelled:
            raise ValueError("No se pueden registrar pagos sobre una deuda anulada.")
        if self.is_paid or self.pending_balance <= Decimal('0.00'):
            raise ValueError("Esta cuenta por pagar ya ha sido saldada.")

        amount = Decimal(str(amount))
        if amount <= Decimal('0.00'):
            raise ValueError("El valor del pago debe ser mayor a cero.")
        if amount > self.pending_balance:
            raise ValueError(
                f"El pago (${amount:,.2f}) supera el saldo pendiente (${self.pending_balance:,.2f})."
            )

        payment = SupplierPayment.objects.create(
            debt=self,
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            user=user,
            notes=notes
        )

        self.paid_amount += amount
        self.pending_balance -= amount
        if self.pending_balance <= Decimal('0.00'):
            self.pending_balance = Decimal('0.00')
            self.is_paid = True
        self.save(update_fields=['paid_amount', 'pending_balance', 'is_paid', 'updated_at'])

        # Registrar egreso financiero por el pago al proveedor
        from finance.models import FinancialCategory, FinancialMovement
        category = FinancialCategory.get_or_create_system_category(
            'Pagos a Proveedores', FinancialCategory.TYPE_EXPENSE
        )
        FinancialMovement.objects.create(
            movement_type=FinancialMovement.TYPE_EXPENSE,
            category=category,
            description=f"Pago a {self.supplier.name} - Compra #{self.purchase.invoice_number}",
            amount=amount,
            payment_method=payment_method,
            user=user,
            notes=notes,
            supplier_payment=payment,
        )

        return payment


class SupplierPayment(models.Model):
    """
    Registro individual de pago/abono realizado a un proveedor.
    """
    PAYMENT_CASH = 'cash'
    PAYMENT_TRANSFER = 'transfer'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, 'Efectivo'),
        (PAYMENT_TRANSFER, 'Transferencia Bancaria'),
    ]

    debt = models.ForeignKey(
        SupplierDebt,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Cuenta por Pagar'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Valor Pagado'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_CASH,
        verbose_name='Método de Pago'
    )
    reference = models.CharField(max_length=100, blank=True, verbose_name='Referencia / Comprobante')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='supplier_payments_made',
        verbose_name='Usuario Responsable'
    )
    notes = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Pago a Proveedor'
        verbose_name_plural = 'Pagos a Proveedores'
        ordering = ['-date']

    def __str__(self):
        return f"Pago ${self.amount} - {self.debt.supplier.name} ({self.date.strftime('%d/%m/%Y')})"
