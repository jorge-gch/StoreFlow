import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from inventory.models import Category, Product, InventoryMovement
from customers.models import Customer
from sales.models import Sale, SaleItem

class SalesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.seller = User.objects.create_user(username='seller_test', password='Password123!')
        self.seller.profile.role = UserProfile.ROLE_EMPLOYEE
        self.seller.profile.save()

        self.admin = User.objects.create_user(username='admin_sales', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.category = Category.objects.create(name='Snacks')
        self.product1 = Product.objects.create(
            name='Papas Margarita Pollo 105g',
            sku='SNK-PAP-105',
            category=self.category,
            cost_price=Decimal('2500.00'),
            sale_price=Decimal('3500.00'),
            stock=50,
            min_stock=10
        )
        self.product2 = Product.objects.create(
            name='Galletas Festival Chocolate',
            sku='SNK-FEST-CHO',
            category=self.category,
            cost_price=Decimal('1000.00'),
            sale_price=Decimal('1500.00'),
            stock=30,
            min_stock=5
        )

        self.customer = Customer.objects.create(
            name='Pedro Infante',
            phone='3005554433'
        )

    def test_invoice_number_generation(self):
        """Verifica que el correlativo se incremente adecuadamente."""
        inv1 = Sale.generate_next_invoice_number()
        self.assertEqual(inv1, 'FAC-000001')

    def test_pos_process_sale_success(self):
        """Procesa una venta multi-producto desde el POS y valida stock e inventario."""
        self.client.login(username='seller_test', password='Password123!')

        payload = [
            {'product_id': self.product1.id, 'quantity': 3},
            {'product_id': self.product2.id, 'quantity': 2},
        ]

        response = self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': 'cash',
            'discount': '500.00',
            'notes': 'Venta rápida de mostrador',
            'items_json': json.dumps(payload),
        })

        # Redirección a detalle de venta
        self.assertEqual(response.status_code, 302)

        # Verificar venta
        sale = Sale.objects.first()
        self.assertIsNotNone(sale)
        # Subtotal: (3 * 3500) + (2 * 1500) = 10500 + 3000 = 13500
        # Total: 13500 - 500 = 13000
        self.assertEqual(sale.subtotal, Decimal('13500.00'))
        self.assertEqual(sale.discount, Decimal('500.00'))
        self.assertEqual(sale.total, Decimal('13000.00'))
        self.assertEqual(sale.items.count(), 2)

        # Verificar descuento de inventario
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock, 47)
        self.assertEqual(self.product2.stock, 28)

        # Verificar Kardex
        mov1 = InventoryMovement.objects.filter(product=self.product1, movement_type='out').first()
        self.assertIsNotNone(mov1)
        self.assertEqual(mov1.quantity, 3)
        self.assertEqual(mov1.previous_stock, 50)
        self.assertEqual(mov1.new_stock, 47)

    def test_pos_rejects_insufficient_stock(self):
        """No permite vender más unidades de las disponibles en inventario."""
        self.client.login(username='seller_test', password='Password123!')

        payload = [
            {'product_id': self.product1.id, 'quantity': 999},
        ]

        response = self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': 'cash',
            'items_json': json.dumps(payload),
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 50)

    def test_sale_cancellation_restores_stock(self):
        """La anulación de una venta restaura el stock y registra en Kardex."""
        # 1. Crear venta inicial
        sale = Sale.objects.create(
            invoice_number='FAC-000001',
            customer=self.customer,
            user=self.seller,
            subtotal=Decimal('7000.00'),
            total=Decimal('7000.00'),
            payment_method='cash'
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            quantity=2,
            unit_price=self.product1.sale_price,
            subtotal=Decimal('7000.00')
        )
        # Descontar stock
        self.product1.adjust_stock(2, 'out', 'Venta FAC-000001', self.seller)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 48)

        # 2. Anular venta como Admin
        self.client.login(username='admin_sales', password='Password123!')
        res_cancel = self.client.post(reverse('sales:sale_cancel', kwargs={'pk': sale.pk}), {
            'cancellation_reason': 'Cliente devolvió producto sellado'
        })
        self.assertEqual(res_cancel.status_code, 302)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_CANCELLED)
        self.assertEqual(sale.cancellation_reason, 'Cliente devolvió producto sellado')

        # Stock restablecido a 50
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 50)
