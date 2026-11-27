import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from suppliers.models import Supplier, Purchase, PurchaseItem, SupplierDebt, SupplierPayment
from inventory.models import Category, Product, InventoryMovement

class SupplierAndPurchasesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_user(username='admin_pur', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.employee = User.objects.create_user(username='emp_pur', password='Password123!')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.supplier = Supplier.objects.create(
            name='Comercializadora Alianza',
            phone='6018889900'
        )

        self.category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Agua Manantial 500ml',
            sku='BEB-AGU-500',
            category=self.category,
            cost_price=Decimal('1200.00'),
            sale_price=Decimal('2000.00'),
            stock=10,
            min_stock=5
        )

    def test_supplier_creation_and_properties(self):
        self.assertEqual(str(self.supplier), 'Comercializadora Alianza')
        self.assertEqual(self.supplier.total_purchases, 0)
        self.assertEqual(self.supplier.total_debt, 0)

    def test_purchase_invoice_correlative(self):
        self.assertEqual(Purchase.generate_next_invoice_number(), 'COM-000001')

    def test_purchase_create_and_stock_increment(self):
        """Registrar una compra debe incrementar el inventario y registrar en Kardex."""
        self.client.login(username='admin_pur', password='Password123!')

        payload = [
            {'product_id': self.product.id, 'quantity': 15, 'unit_cost': 1300.00}
        ]

        response = self.client.post(reverse('suppliers:purchase_create'), {
            'supplier_id': self.supplier.id,
            'supplier_invoice': 'FAC-PROV-999',
            'payment_method': 'cash',
            'update_costs': 'on',
            'items_json': json.dumps(payload),
        })

        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.total, Decimal('19500.00'))

        # Validar incremento de stock: 10 + 15 = 25
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 25)
        # Costo actualizado
        self.assertEqual(self.product.cost_price, Decimal('1300.00'))

        # Validar Kardex
        mov = InventoryMovement.objects.filter(product=self.product, movement_type='in').first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.quantity, 15)
        self.assertEqual(mov.previous_stock, 10)
        self.assertEqual(mov.new_stock, 25)

    def test_purchase_cancellation_restores_stock(self):
        """La anulación de una compra descuenta el stock recibido."""
        self.client.login(username='admin_pur', password='Password123!')

        # Crear compra directamente
        purchase = Purchase.objects.create(
            invoice_number='COM-000001',
            supplier=self.supplier,
            user=self.admin,
            total=Decimal('6000.00'),
            payment_method='cash'
        )
        PurchaseItem.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=5,
            unit_cost=Decimal('1200.00'),
            subtotal=Decimal('6000.00')
        )
        # Incrementar stock
        self.product.adjust_stock(5, 'in', 'Compra COM-000001', self.admin)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

        # Anular compra
        res = self.client.post(reverse('suppliers:purchase_cancel', kwargs={'pk': purchase.pk}), {
            'cancellation_reason': 'Mercancía en mal estado devuelta al distribuidor'
        })
        self.assertEqual(res.status_code, 302)

        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.STATUS_CANCELLED)

        # Stock revertido: 15 - 5 = 10
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_purchase_cancellation_prevented_if_insufficient_stock(self):
        """Si el stock se vendió y es menor a la compra, no se permite anular."""
        purchase = Purchase.objects.create(
            invoice_number='COM-000002',
            supplier=self.supplier,
            user=self.admin,
            total=Decimal('12000.00')
        )
        PurchaseItem.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('1200.00'),
            subtotal=Decimal('12000.00')
        )
        # Simular que solo quedan 2 unidades disponibles
        self.product.stock = 2
        self.product.save()

        with self.assertRaises(ValueError):
            purchase.cancel(user=self.admin, reason='Intento de anulación sin stock')

    def test_employee_forbidden_to_create_purchase(self):
        self.client.login(username='emp_pur', password='Password123!')
        response = self.client.get(reverse('suppliers:purchase_create'))
        self.assertEqual(response.status_code, 302)


class SupplierDebtTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_user(username='admin_sdebt', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.employee = User.objects.create_user(username='emp_sdebt', password='Password123!')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.supplier = Supplier.objects.create(name='Proveedor Crédito S.A.', phone='6010001122')
        self.category = Category.objects.create(name='Lácteos')
        self.product = Product.objects.create(
            name='Leche Entera 1L',
            sku='LAC-001',
            category=self.category,
            cost_price=Decimal('3000.00'),
            sale_price=Decimal('4500.00'),
            stock=5,
            min_stock=2,
        )

    def test_partial_purchase_auto_creates_debt_and_initial_payment(self):
        self.client.login(username='admin_sdebt', password='Password123!')
        payload = [{'product_id': self.product.id, 'quantity': 10, 'unit_cost': 3000.00}]

        response = self.client.post(reverse('suppliers:purchase_create'), {
            'supplier_id': self.supplier.id,
            'payment_method': Purchase.PAYMENT_PARTIAL,
            'initial_payment': '10000.00',
            'items_json': json.dumps(payload),
        })
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.first()
        self.assertIsNotNone(purchase)
        self.assertTrue(hasattr(purchase, 'debt'))
        self.assertEqual(purchase.debt.total_amount, Decimal('30000.00'))
        self.assertEqual(purchase.debt.paid_amount, Decimal('10000.00'))
        self.assertEqual(purchase.debt.pending_balance, Decimal('20000.00'))
        self.assertEqual(purchase.debt.payments.count(), 1)

        # Registrar pago adicional vía vista
        pay_res = self.client.post(reverse('suppliers:debt_register_payment', kwargs={'pk': purchase.debt.pk}), {
            'amount': '20000.00',
            'payment_method': SupplierPayment.PAYMENT_TRANSFER,
            'reference': 'TRF-8821',
            'notes': 'Saldo total',
        })
        self.assertEqual(pay_res.status_code, 302)
        purchase.debt.refresh_from_db()
        self.assertTrue(purchase.debt.is_paid)
        self.assertEqual(purchase.debt.pending_balance, Decimal('0.00'))

    def test_supplier_overpayment_raises_error(self):
        purchase = Purchase.objects.create(
            invoice_number='COM-DEBT-01',
            supplier=self.supplier,
            user=self.admin,
            total=Decimal('5000.00'),
            payment_method=Purchase.PAYMENT_CREDIT,
        )
        debt = SupplierDebt.objects.create(
            supplier=self.supplier,
            purchase=purchase,
            total_amount=Decimal('5000.00'),
            paid_amount=Decimal('0.00'),
            pending_balance=Decimal('5000.00'),
        )
        with self.assertRaises(ValueError):
            debt.register_payment(amount=Decimal('6000.00'), payment_method=SupplierPayment.PAYMENT_CASH, user=self.admin)

    def test_employee_forbidden_to_access_supplier_debts(self):
        self.client.login(username='emp_sdebt', password='Password123!')
        response = self.client.get(reverse('suppliers:debt_list'))
        self.assertEqual(response.status_code, 302)
