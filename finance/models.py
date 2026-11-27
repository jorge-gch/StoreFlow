from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone


class FinancialCategory(models.Model):
    """
    Categorías para clasificar ingresos y egresos de la tienda.
    """
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'

    TYPE_CHOICES = [
        (TYPE_INCOME, 'Ingreso'),
        (TYPE_EXPENSE, 'Egreso'),
    ]

    name = models.CharField(max_length=100, verbose_name='Nombre de Categoría')
    movement_type = models.CharField(
        max_length=15,
        choices=TYPE_CHOICES,
        verbose_name='Tipo de Movimiento'
    )
    description = models.TextField(blank=True, verbose_name='Descripción')
    is_system = models.BooleanField(default=False, verbose_name='Categoría del Sistema')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        verbose_name = 'Categoría Financiera'
        verbose_name_plural = 'Categorías Financieras'
        ordering = ['movement_type', 'name']
        unique_together = ('name', 'movement_type')

    def __str__(self):
        return f"{self.name} ({self.get_movement_type_display()})"

    @classmethod
    def get_or_create_system_category(cls, name, movement_type):
        """
        Obtiene o crea una categoría reservada para movimientos automáticos del sistema.
        """
        category, _ = cls.objects.get_or_create(
            name=name,
            movement_type=movement_type,
            defaults={'is_system': True, 'is_active': True}
        )
        return category


class FinancialMovement(models.Model):
    """
    Registro de movimientos de dinero (ingresos y egresos) de la tienda.
    Incluye vínculos opcionales a ventas, compras y abonos para evitar duplicidad.
    """
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'

    TYPE_CHOICES = [
        (TYPE_INCOME, 'Ingreso'),
        (TYPE_EXPENSE, 'Egreso'),
    ]

    PAYMENT_CASH = 'cash'
    PAYMENT_TRANSFER = 'transfer'

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_CASH, 'Efectivo'),
        (PAYMENT_TRANSFER, 'Transferencia Bancaria'),
    ]

    movement_type = models.CharField(
        max_length=15,
        choices=TYPE_CHOICES,
        verbose_name='Tipo de Movimiento'
    )
    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        related_name='movements',
        verbose_name='Categoría'
    )
    description = models.CharField(max_length=255, verbose_name='Descripción')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Valor'
    )
    date = models.DateTimeField(default=timezone.now, verbose_name='Fecha y Hora')
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_CASH,
        verbose_name='Método de Pago'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='financial_movements',
        verbose_name='Usuario Responsable'
    )
    is_cancelled = models.BooleanField(default=False, verbose_name='Anulado')
    notes = models.TextField(blank=True, verbose_name='Observaciones')

    # Vínculos de origen para evitar doble contabilización
    sale = models.OneToOneField(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='financial_movement',
        verbose_name='Venta Asociada'
    )
    customer_payment = models.OneToOneField(
        'customers.CustomerPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='financial_movement',
        verbose_name='Abono de Cliente'
    )
    purchase = models.OneToOneField(
        'suppliers.Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='financial_movement',
        verbose_name='Compra Asociada'
    )
    supplier_payment = models.OneToOneField(
        'suppliers.SupplierPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='financial_movement',
        verbose_name='Pago a Proveedor'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')

    class Meta:
        verbose_name = 'Movimiento Financiero'
        verbose_name_plural = 'Movimientos Financieros'
        ordering = ['-date', '-id']

    def __str__(self):
        sign = '+' if self.movement_type == self.TYPE_INCOME else '-'
        return f"{sign}${self.amount:,.2f} | {self.category.name} - {self.description}"

    @property
    def is_automatic(self):
        return any([self.sale_id, self.customer_payment_id, self.purchase_id, self.supplier_payment_id])
