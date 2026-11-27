import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from customers.models import Customer, CustomerDebt, CustomerPayment
from inventory.models import Category, Product
from sales.models import Sale

class CustomerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='c_tester', password='Password123!')
        self.user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.user.profile.save()

        self.customer = Customer.objects.create(
            name='Carlos Mendoza',
            document_id='12345678',
            phone='3001112233',
            email='carlos@correo.com'
        )

    def test_customer_creation(self):
        self.assertEqual(str(self.customer), 'Carlos Mendoza (12345678)')
        self.assertEqual(self.customer.total_purchases, 0)
        self.assertEqual(self.customer.total_debt, 0)

    def test_customer_list_view(self):
        self.client.login(username='c_tester', password='Password123!')
        response = self.client.get(reverse('customers:customer_list'), {'q': 'Mendoza'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carlos Mendoza')
        self.assertContains(response, '3001112233')

    def test_customer_create_view(self):
        self.client.login(username='c_tester', password='Password123!')
        response = self.client.post(reverse('customers:customer_create'), {
            'name': 'Beatriz Pinzón',
            'document_id': '87654321',
            'phone': '3109998877',
            'email': 'betty@correo.com',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(name='Beatriz Pinzón').exists())


class CustomerDebtTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_debt', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.customer = Customer.objects.create(name='Test Cliente', phone='3001234567')
        self.category = Category.objects.create(name='General')
        self.product = Product.objects.create(
            name='Producto Test',
            sku='PROD-001',
            category=self.category,
            cost_price=Decimal('50.00'),
            sale_price=Decimal('100.00'),
            stock=10,
            min_stock=2,
        )
        self.sale = Sale.objects.create(
            invoice_number='FAC-TEST-001',
            customer=self.customer,
            user=self.admin,
            payment_method=Sale.PAYMENT_CREDIT,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
        )

    def test_create_and_register_partial_and_full_payment(self):
        debt = CustomerDebt.objects.create(
            customer=self.customer,
            sale=self.sale,
            total_amount=Decimal('100.00'),
            paid_amount=Decimal('0.00'),
            pending_balance=Decimal('100.00'),
        )
        debt.register_payment(
            amount=Decimal('60.00'),
            payment_method=CustomerPayment.PAYMENT_CASH,
            user=self.admin,
        )
        debt.refresh_from_db()
        self.assertEqual(debt.paid_amount, Decimal('60.00'))
        self.assertEqual(debt.pending_balance, Decimal('40.00'))
        self.assertFalse(debt.is_paid)

        debt.register_payment(
            amount=Decimal('40.00'),
            payment_method=CustomerPayment.PAYMENT_TRANSFER,
            user=self.admin,
        )
        debt.refresh_from_db()
        self.assertEqual(debt.pending_balance, Decimal('0.00'))
        self.assertTrue(debt.is_paid)

    def test_overpayment_and_zero_payment_raise_error(self):
        debt = CustomerDebt.objects.create(
            customer=self.customer,
            sale=self.sale,
            total_amount=Decimal('100.00'),
            paid_amount=Decimal('0.00'),
            pending_balance=Decimal('100.00'),
        )
        with self.assertRaises(ValueError):
            debt.register_payment(amount=Decimal('150.00'), payment_method=CustomerPayment.PAYMENT_CASH, user=self.admin)
        with self.assertRaises(ValueError):
            debt.register_payment(amount=Decimal('0.00'), payment_method=CustomerPayment.PAYMENT_CASH, user=self.admin)

    def test_credit_sale_pos_auto_creates_debt_and_cancel_cancels_debt(self):
        self.client.login(username='admin_debt', password='Password123!')
        response = self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': Sale.PAYMENT_CREDIT,
            'discount': '0',
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 2}]),
        })
        self.assertEqual(response.status_code, 302)
        new_sale = Sale.objects.exclude(pk=self.sale.pk).first()
        self.assertIsNotNone(new_sale)
        self.assertTrue(hasattr(new_sale, 'debt'))
        self.assertEqual(new_sale.debt.pending_balance, Decimal('200.00'))

        # Registrar abono vía vista
        pay_res = self.client.post(reverse('customers:debt_register_payment', kwargs={'pk': new_sale.debt.pk}), {
            'amount': '50.00',
            'payment_method': CustomerPayment.PAYMENT_CASH,
            'notes': 'Primer abono',
        })
        self.assertEqual(pay_res.status_code, 302)
        new_sale.debt.refresh_from_db()
        self.assertEqual(new_sale.debt.pending_balance, Decimal('150.00'))

        # Anular venta debe anular la deuda
        new_sale.cancel(user=self.admin, reason='Error en factura')
        new_sale.debt.refresh_from_db()
        self.assertTrue(new_sale.debt.is_cancelled)
