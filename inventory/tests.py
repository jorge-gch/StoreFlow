from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from inventory.models import Category, Product, InventoryMovement

class InventoryTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(username='admin_inv', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        # Employee user
        self.employee = User.objects.create_user(username='emp_inv', password='Password123!')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        # Category
        self.category = Category.objects.create(name='Bebidas', description='Gaseosas y jugos')

        # Product
        self.product = Product.objects.create(
            name='Jugo Hit 500ml',
            sku='BEB-HIT-500',
            category=self.category,
            cost_price=Decimal('1500.00'),
            sale_price=Decimal('2200.00'),
            stock=20,
            min_stock=5
        )

    def test_product_creation_and_properties(self):
        """Verifica cálculos y propiedades del producto."""
        self.assertEqual(str(self.product), 'Jugo Hit 500ml (BEB-HIT-500)')
        self.assertEqual(self.product.profit_margin, Decimal('700.00'))
        self.assertFalse(self.product.is_low_stock)

        # Probar alerta de bajo stock
        self.product.stock = 4
        self.assertTrue(self.product.is_low_stock)

    def test_stock_adjustment_in_and_out(self):
        """Verifica que el método adjust_stock actualice existencias y cree el Kardex."""
        # Entrada de 10 unidades
        mov_in = self.product.adjust_stock(
            quantity=10,
            movement_type=InventoryMovement.MOVEMENT_IN,
            reference='Compra inicial',
            user=self.admin
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 30)
        self.assertEqual(mov_in.previous_stock, 20)
        self.assertEqual(mov_in.new_stock, 30)

        # Salida de 5 unidades
        mov_out = self.product.adjust_stock(
            quantity=5,
            movement_type=InventoryMovement.MOVEMENT_OUT,
            reference='Venta Mostrador',
            user=self.employee
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 25)
        self.assertEqual(mov_out.previous_stock, 30)
        self.assertEqual(mov_out.new_stock, 25)

    def test_stock_adjustment_insufficient_stock(self):
        """Salida superior a existencias debe lanzar ValueError."""
        with self.assertRaises(ValueError):
            self.product.adjust_stock(
                quantity=100,
                movement_type=InventoryMovement.MOVEMENT_OUT,
                reference='Salida excesiva',
                user=self.admin
            )

    def test_permissions_product_create_and_update(self):
        """Solo administradores pueden crear o modificar productos."""
        # Empleado no puede crear productos (debe ser redirigido con error)
        self.client.login(username='emp_inv', password='Password123!')
        res_emp = self.client.get(reverse('inventory:product_create'))
        self.assertEqual(res_emp.status_code, 302)

        # Administrador sí puede acceder
        self.client.login(username='admin_inv', password='Password123!')
        res_adm = self.client.get(reverse('inventory:product_create'))
        self.assertEqual(res_adm.status_code, 200)

    def test_product_list_view_and_filtering(self):
        """Listado de productos accesible por usuarios autenticados."""
        self.client.login(username='emp_inv', password='Password123!')
        response = self.client.get(reverse('inventory:product_list'), {'q': 'Hit'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jugo Hit 500ml')
        self.assertContains(response, 'BEB-HIT-500')
