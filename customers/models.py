from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone


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
        total = self.debts.filter(is_paid=False, is_cancelled=False).aggregate(
            models.Sum('pending_balance')
        )['pending_balance__sum']
        return total or Decimal('0.00')


class CustomerDebt(models.Model):
    """
    Cuenta por cobrar asociada a una venta a crédito o pago parcial.
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='debts',
        verbose_name='Cliente'
    )
    sale = models.OneToOneField(
        'sales.Sale',
        on_delete=models.CASCADE,
        related_name='debt',
        verbose_name='Venta Asociada'
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
        verbose_name='Total Abonado'
    )
    pending_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Saldo Pendiente'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='Fecha de Vencimiento')
    is_paid = models.BooleanField(default=False, verbose_name='Pagada en su totalidad')
    is_cancelled = models.BooleanField(default=False, verbose_name='Anulada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Cuenta por Cobrar'
        verbose_name_plural = 'Cuentas por Cobrar'
        ordering = ['-created_at']

    def __str__(self):
        return f"Deuda #{self.sale.invoice_number} - {self.customer.name} (Saldo: ${self.pending_balance})"

    @property
    def is_overdue(self):
        """Indica si la deuda está vencida."""
        if self.is_paid or self.is_cancelled or not self.due_date:
            return False
        return self.due_date < timezone.localdate()

    @transaction.atomic
    def register_payment(self, amount, payment_method, user, notes=""):
        """
        Registra un abono individual sobre la deuda de forma atómica.
        """
        if self.is_cancelled:
            raise ValueError("No se pueden registrar abonos sobre una deuda anulada.")
        if self.is_paid or self.pending_balance <= Decimal('0.00'):
            raise ValueError("Esta deuda ya ha sido saldada en su totalidad.")

        amount = Decimal(str(amount))
        if amount <= Decimal('0.00'):
            raise ValueError("El valor del abono debe ser mayor a cero.")
        if amount > self.pending_balance:
            raise ValueError(
                f"El abono (${amount:,.2f}) supera el saldo pendiente (${self.pending_balance:,.2f})."
            )

        payment = CustomerPayment.objects.create(
            debt=self,
            amount=amount,
            payment_method=payment_method,
            user=user,
            notes=notes
        )

        self.paid_amount += amount
        self.pending_balance -= amount
        if self.pending_balance <= Decimal('0.00'):
            self.pending_balance = Decimal('0.00')
            self.is_paid = True
        self.save(update_fields=['paid_amount', 'pending_balance', 'is_paid', 'updated_at'])

        # Registrar ingreso financiero por el abono (evitando duplicados)
        from finance.models import FinancialCategory, FinancialMovement
        category = FinancialCategory.get_or_create_system_category(
            'Abonos de Clientes', FinancialCategory.TYPE_INCOME
        )
        FinancialMovement.objects.create(
            movement_type=FinancialMovement.TYPE_INCOME,
            category=category,
            description=f"Abono Cliente {self.customer.name} - Factura #{self.sale.invoice_number}",
            amount=amount,
            payment_method=payment_method,
            user=user,
            notes=notes,
            customer_payment=payment,
        )

        return payment


class CustomerPayment(models.Model):
    """
    Registro individual de abono realizado por un cliente a una deuda.
    """
    PAYMENT_CASH = 'cash'
    PAYMENT_TRANSFER = 'transfer'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, 'Efectivo'),
        (PAYMENT_TRANSFER, 'Transferencia Bancaria'),
    ]

    debt = models.ForeignKey(
        CustomerDebt,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Cuenta por Cobrar'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Valor Abonado'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_CASH,
        verbose_name='Método de Pago'
    )
    date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='customer_payments_received',
        verbose_name='Usuario que Recibe'
    )
    notes = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Abono de Cliente'
        verbose_name_plural = 'Abonos de Clientes'
        ordering = ['-date']

    def __str__(self):
        return f"Abono ${self.amount} - {self.debt.customer.name} ({self.date.strftime('%d/%m/%Y')})"
