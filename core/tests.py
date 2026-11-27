from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile

class AuthenticationAndRolesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Crear usuario admin
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='Password123!',
            email='admin@test.com',
            first_name='Admin',
            last_name='User'
        )
        self.admin_user.profile.role = UserProfile.ROLE_ADMIN
        self.admin_user.profile.save()

        # Crear usuario empleado
        self.employee_user = User.objects.create_user(
            username='employee_test',
            password='Password123!',
            email='employee@test.com',
            first_name='Employee',
            last_name='User'
        )
        self.employee_user.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee_user.profile.save()

    def test_unauthenticated_user_redirected_to_login(self):
        """Usuarios no autenticados deben ser redirigidos al login."""
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core:login'), response.url)

    def test_login_successful(self):
        """Inicio de sesión exitoso redirige al dashboard."""
        response = self.client.post(reverse('core:login'), {
            'username': 'admin_test',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:dashboard'))

    def test_login_failed_invalid_credentials(self):
        """Credenciales inválidas no inician sesión y muestran mensaje de error."""
        response = self.client.post(reverse('core:login'), {
            'username': 'admin_test',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/login.html')

    def test_logout(self):
        """Cierre de sesión redirige a la página de login."""
        self.client.login(username='admin_test', password='Password123!')
        response = self.client.get(reverse('core:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('core:login'))

    def test_user_profile_signal_creation(self):
        """La señal post_save debe crear automáticamente un UserProfile al crear un User."""
        new_user = User.objects.create_user(username='nuevo_usuario', password='password123')
        self.assertTrue(hasattr(new_user, 'profile'))
        self.assertEqual(new_user.profile.role, UserProfile.ROLE_EMPLOYEE)

    def test_role_properties(self):
        """Verifica las propiedades is_admin e is_employee."""
        self.assertTrue(self.admin_user.profile.is_admin)
        self.assertFalse(self.admin_user.profile.is_employee)
        self.assertFalse(self.employee_user.profile.is_admin)
        self.assertTrue(self.employee_user.profile.is_employee)

    def test_dashboard_renders_for_authenticated_users(self):
        """Tanto admin como empleado pueden ver el dashboard con sus métricas."""
        self.client.login(username='admin_test', password='Password123!')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/dashboard.html')
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Administrador')

    def test_profile_update(self):
        """El usuario puede actualizar sus datos personales desde el perfil."""
        self.client.login(username='employee_test', password='Password123!')
        response = self.client.post(reverse('core:profile'), {
            'first_name': 'Laura Modificada',
            'last_name': 'Vendedora',
            'email': 'laura_mod@test.com',
            'phone': '3009998877'
        })
        self.assertEqual(response.status_code, 302)
        self.employee_user.refresh_from_db()
        self.assertEqual(self.employee_user.first_name, 'Laura Modificada')
        self.assertEqual(self.employee_user.profile.phone, '3009998877')


class EndToEndConsistencyTestCase(TestCase):
    """
    Prueba integral de flujo completo: compra -> venta contado -> venta crédito -> abono -> dashboard.
    Valida consistencia entre inventario, cartera y finanzas.
    """
    def test_full_store_lifecycle_consistency(self):
        import json
        from decimal import Decimal
        from inventory.models import Category, Product
        from customers.models import Customer, CustomerPayment
        from suppliers.models import Supplier, Purchase
        from sales.models import Sale
        from finance.models import FinancialMovement

        admin = User.objects.create_user(username='e2e_admin', password='Password123!')
        admin.profile.role = UserProfile.ROLE_ADMIN
        admin.profile.save()

        cat = Category.objects.create(name='Bebidas')
        product = Product.objects.create(
            name='Jugo Natural',
            sku='BEB-010',
            category=cat,
            cost_price=Decimal('2000.00'),
            sale_price=Decimal('3500.00'),
            stock=0,
            min_stock=5,
        )
        supplier = Supplier.objects.create(name='Distribuidora Sur', phone='6011234567')
        customer = Customer.objects.create(name='María López', phone='3001234567')

        self.client.login(username='e2e_admin', password='Password123!')

        # 1. Compra de 10 unidades de contado ($20,000 egreso)
        self.client.post(reverse('suppliers:purchase_create'), {
            'supplier_id': supplier.id,
            'payment_method': Purchase.PAYMENT_CASH,
            'items_json': json.dumps([{'product_id': product.id, 'quantity': 10, 'unit_cost': 2000.00}]),
        })
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

        # 2. Venta de 3 unidades de contado ($10,500 ingreso)
        self.client.post(reverse('sales:pos'), {
            'customer_id': customer.id,
            'payment_method': Sale.PAYMENT_CASH,
            'discount': '0',
            'items_json': json.dumps([{'product_id': product.id, 'quantity': 3}]),
        })

        # 3. Venta de 2 unidades a crédito ($7,000 por cobrar, $0 ingreso inmediato)
        self.client.post(reverse('sales:pos'), {
            'customer_id': customer.id,
            'payment_method': Sale.PAYMENT_CREDIT,
            'discount': '0',
            'items_json': json.dumps([{'product_id': product.id, 'quantity': 2}]),
        })
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)  # 10 - 3 - 2 = 5

        credit_sale = Sale.objects.filter(payment_method=Sale.PAYMENT_CREDIT).first()
        self.assertEqual(credit_sale.debt.pending_balance, Decimal('7000.00'))

        # 4. Abono de $4,000 a la deuda
        self.client.post(reverse('customers:debt_register_payment', kwargs={'pk': credit_sale.debt.pk}), {
            'amount': '4000.00',
            'payment_method': CustomerPayment.PAYMENT_TRANSFER,
        })

        # Verificar consistencia en Dashboard
        res = self.client.get(reverse('core:dashboard'))
        self.assertEqual(res.status_code, 200)
        metrics = res.context['metrics']
        self.assertEqual(metrics['income_month'], Decimal('14500.00'))   # 10,500 + 4,000
        self.assertEqual(metrics['expenses_month'], Decimal('20000.00')) # 20,000 compra
        self.assertEqual(metrics['pending_receivables'], Decimal('3000.00'))  # 7,000 - 4,000
        self.assertEqual(FinancialMovement.objects.filter(is_cancelled=False).count(), 3)
