from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal

class Category(models.Model):
    """
    Categoría para clasificación de productos en inventario.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_products(self):
        return self.products.filter(is_active=True).count()


class Product(models.Model):
    """
    Modelo de producto con control de SKU, stock y precios.
    """
    name = models.CharField(max_length=200, verbose_name='Nombre del Producto')
    sku = models.CharField(max_length=50, unique=True, verbose_name='Código / SKU')
    description = models.TextField(blank=True, verbose_name='Descripción')
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Categoría'
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio de Compra'
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio de Venta'
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Cantidad Disponible'
    )
    min_stock = models.PositiveIntegerField(
        default=5,
        verbose_name='Stock Mínimo'
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        return self.stock <= self.min_stock

    @property
    def profit_margin(self):
        """Margen estimado de ganancia unitario."""
        return self.sale_price - self.cost_price

    @transaction.atomic
    def adjust_stock(self, quantity, movement_type, reference, user, notes=""):
        """
        Ajusta el inventario de forma atómica y genera el movimiento en el Kardex.
        quantity: número entero positivo.
        movement_type: 'in' (entrada), 'out' (salida), 'adjustment' (ajuste).
        """
        previous_stock = self.stock

        if movement_type == InventoryMovement.MOVEMENT_IN:
            new_stock = previous_stock + quantity
        elif movement_type == InventoryMovement.MOVEMENT_OUT:
            if previous_stock < quantity:
                raise ValueError(f"Stock insuficiente. Disponible: {previous_stock}, Solicitado: {quantity}")
            new_stock = previous_stock - quantity
        elif movement_type == InventoryMovement.MOVEMENT_ADJUSTMENT:
            new_stock = quantity
            quantity = abs(new_stock - previous_stock)
        else:
            raise ValueError("Tipo de movimiento inválido.")

        self.stock = new_stock
        self.save(update_fields=['stock', 'updated_at'])

        movement = InventoryMovement.objects.create(
            product=self,
            movement_type=movement_type,
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reference=reference,
            user=user,
            notes=notes
        )
        return movement


class InventoryMovement(models.Model):
    """
    Registro histórico de movimientos de inventario (Kardex).
    """
    MOVEMENT_IN = 'in'
    MOVEMENT_OUT = 'out'
    MOVEMENT_ADJUSTMENT = 'adjustment'

    MOVEMENT_CHOICES = [
        (MOVEMENT_IN, 'Entrada'),
        (MOVEMENT_OUT, 'Salida'),
        (MOVEMENT_ADJUSTMENT, 'Ajuste de Inventario'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name='Producto'
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_CHOICES,
        verbose_name='Tipo de Movimiento'
    )
    quantity = models.PositiveIntegerField(verbose_name='Cantidad')
    previous_stock = models.IntegerField(verbose_name='Stock Anterior')
    new_stock = models.IntegerField(verbose_name='Nuevo Stock')
    reference = models.CharField(max_length=150, verbose_name='Referencia / Motivo')
    notes = models.TextField(blank=True, verbose_name='Notas adicionales')
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='inventory_movements',
        verbose_name='Usuario Responsable'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} ({self.quantity} uds)"
