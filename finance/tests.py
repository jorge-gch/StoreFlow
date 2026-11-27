import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from inventory.models import Category, Product
from customers.models import Customer, CustomerPayment
from suppliers.models import Supplier, Purchase, SupplierPayment
from sales.models import Sale
from finance.models import FinancialCategory, FinancialMovement


class FinanceModuleTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_user(username='admin_fin', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.employee = User.objects.create_user(username='emp_fin', password='Password123!')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.customer = Customer.objects.create(name='Cliente Finanzas', phone='3005556677')
        self.supplier = Supplier.objects.create(name='Proveedor Finanzas', phone='6015556677')
        self.inv_cat = Category.objects.create(name='Abarrotes')
        self.product = Product.objects.create(
            name='Arroz 1Kg',
            sku='ABA-001',
            category=self.inv_cat,
            cost_price=Decimal('2500.00'),
            sale_price=Decimal('4000.00'),
            stock=50,
            min_stock=5,
        )

    def test_cash_sale_creates_single_income_movement_and_cancel_reverts_it(self):
        self.client.login(username='admin_fin', password='Password123!')
        res = self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': Sale.PAYMENT_CASH,
            'discount': '0',
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 3}]),
        })
        self.assertEqual(res.status_code, 302)

        sale = Sale.objects.first()
        self.assertEqual(FinancialMovement.objects.filter(sale=sale, is_cancelled=False).count(), 1)
        mov = sale.financial_movement
        self.assertEqual(mov.movement_type, FinancialMovement.TYPE_INCOME)
        self.assertEqual(mov.amount, Decimal('12000.00'))

        # Anular venta debe anular el movimiento financiero
        sale.cancel(user=self.admin, reason='Devolución')
        mov.refresh_from_db()
        self.assertTrue(mov.is_cancelled)

    def test_credit_sale_does_not_create_income_until_payment(self):
        self.client.login(username='admin_fin', password='Password123!')
        self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': Sale.PAYMENT_CREDIT,
            'discount': '0',
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 2}]),
        })
        sale = Sale.objects.first()
        # No debe existir ingreso al crear venta a crédito
        self.assertEqual(FinancialMovement.objects.filter(is_cancelled=False).count(), 0)

        # Registrar abono parcial de 3000
        sale.debt.register_payment(
            amount=Decimal('3000.00'),
            payment_method=CustomerPayment.PAYMENT_CASH,
            user=self.admin,
        )
        self.assertEqual(FinancialMovement.objects.filter(is_cancelled=False).count(), 1)
        mov = FinancialMovement.objects.first()
        self.assertEqual(mov.movement_type, FinancialMovement.TYPE_INCOME)
        self.assertEqual(mov.amount, Decimal('3000.00'))

    def test_partial_sale_records_only_initial_payment_no_double_counting(self):
        self.client.login(username='admin_fin', password='Password123!')
        self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': Sale.PAYMENT_PARTIAL,
            'initial_payment': '2500.00',
            'discount': '0',
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 2}]),  # Total 8000
        })
        movements = FinancialMovement.objects.filter(is_cancelled=False)
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().amount, Decimal('2500.00'))

    def test_credit_purchase_vs_cash_purchase_finance_integration(self):
        self.client.login(username='admin_fin', password='Password123!')
        # Compra de contado: genera egreso inmediato
        self.client.post(reverse('suppliers:purchase_create'), {
            'supplier_id': self.supplier.id,
            'payment_method': Purchase.PAYMENT_TRANSFER,
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 4, 'unit_cost': 2500.00}]),
        })
        self.assertEqual(
            FinancialMovement.objects.filter(movement_type=FinancialMovement.TYPE_EXPENSE, is_cancelled=False).count(),
            1,
        )

        # Compra a crédito: no genera egreso hasta pagar
        self.client.post(reverse('suppliers:purchase_create'), {
            'supplier_id': self.supplier.id,
            'payment_method': Purchase.PAYMENT_CREDIT,
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 4, 'unit_cost': 2500.00}]),
        })
        self.assertEqual(
            FinancialMovement.objects.filter(movement_type=FinancialMovement.TYPE_EXPENSE, is_cancelled=False).count(),
            1,
        )

        credit_purchase = Purchase.objects.filter(payment_method=Purchase.PAYMENT_CREDIT).first()
        credit_purchase.debt.register_payment(
            amount=Decimal('4000.00'),
            payment_method=SupplierPayment.PAYMENT_CASH,
            user=self.admin,
        )
        self.assertEqual(
            FinancialMovement.objects.filter(movement_type=FinancialMovement.TYPE_EXPENSE, is_cancelled=False).count(),
            2,
        )

    def test_manual_movement_and_employee_restriction(self):
        # Empleado no puede acceder
        self.client.login(username='emp_fin', password='Password123!')
        res_emp = self.client.get(reverse('finance:movement_list'))
        self.assertEqual(res_emp.status_code, 302)

        # Admin crea gasto manual de Arriendo
        self.client.login(username='admin_fin', password='Password123!')
        cat = FinancialCategory.objects.create(name='Arriendo Local', movement_type=FinancialCategory.TYPE_EXPENSE)
        res = self.client.post(reverse('finance:movement_create'), {
            'movement_type': FinancialMovement.TYPE_EXPENSE,
            'category': cat.id,
            'description': 'Arriendo noviembre',
            'amount': '1500000.00',
            'date': '2026-11-26T10:00',
            'payment_method': FinancialMovement.PAYMENT_TRANSFER,
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(FinancialMovement.objects.filter(description='Arriendo noviembre').count(), 1)
