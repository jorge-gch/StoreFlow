from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile
from inventory.models import Category, Product, InventoryMovement

class Command(BaseCommand):
    help = 'Crea usuarios de prueba, categorías y productos iniciales.'

    def handle(self, *args, **options):
        # 1. Crear Superusuario / Admin
        admin_user, created_admin = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@storeflow.local',
                'first_name': 'Carlos',
                'last_name': 'Administrador',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created_admin:
            admin_user.set_password('admin1234')
            admin_user.save()
            admin_user.profile.role = UserProfile.ROLE_ADMIN
            admin_user.profile.phone = '3001234567'
            admin_user.profile.save()
            self.stdout.write(self.style.SUCCESS('Usuario Administrador creado: admin / admin1234'))

        # 2. Crear Usuario Empleado
        employee_user, created_emp = User.objects.get_or_create(
            username='empleado',
            defaults={
                'email': 'empleado@storeflow.local',
                'first_name': 'Laura',
                'last_name': 'Vendedora',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        if created_emp:
            employee_user.set_password('empleado1234')
            employee_user.save()
            employee_user.profile.role = UserProfile.ROLE_EMPLOYEE
            employee_user.profile.phone = '3119876543'
            employee_user.profile.save()
            self.stdout.write(self.style.SUCCESS('Usuario Empleado creado: empleado / empleado1234'))

        # 3. Crear Categorías Iniciales
        cats_data = [
            ('Abarrotes', 'Granos, harinas, pastas y aceites de primera necesidad.'),
            ('Bebidas', 'Gaseosas, jugos, aguas y bebidas hidratantes.'),
            ('Lácteos', 'Leches, quesos, yogures y derivados lácteos.'),
            ('Limpieza', 'Detergentes, jabones y artículos para aseo del hogar.'),
        ]

        categories_map = {}
        for name, desc in cats_data:
            cat, _ = Category.objects.get_or_create(name=name, defaults={'description': desc})
            categories_map[name] = cat
        self.stdout.write(self.style.SUCCESS('Categorías iniciales creadas.'))

        # 4. Crear Productos de Demostración con Kardex
        sample_products = [
            {
                'sku': 'ABA-001',
                'name': 'Arroz Diana 1000g',
                'category': categories_map['Abarrotes'],
                'cost_price': Decimal('3800.00'),
                'sale_price': Decimal('4800.00'),
                'stock': 45,
                'min_stock': 10,
            },
            {
                'sku': 'ABA-002',
                'name': 'Aceite Premier 900ml',
                'category': categories_map['Abarrotes'],
                'cost_price': Decimal('7500.00'),
                'sale_price': Decimal('9200.00'),
                'stock': 4,  # Stock bajo alerta
                'min_stock': 8,
            },
            {
                'sku': 'BEB-001',
                'name': 'Coca-Cola 1.5L No Retornable',
                'category': categories_map['Bebidas'],
                'cost_price': Decimal('4200.00'),
                'sale_price': Decimal('5500.00'),
                'stock': 28,
                'min_stock': 12,
            },
            {
                'sku': 'LAC-001',
                'name': 'Leche Alquería Entera 1100ml',
                'category': categories_map['Lácteos'],
                'cost_price': Decimal('3900.00'),
                'sale_price': Decimal('4900.00'),
                'stock': 3,  # Stock bajo alerta
                'min_stock': 10,
            },
            {
                'sku': 'LIM-001',
                'name': 'Detergente Fab 1000g',
                'category': categories_map['Limpieza'],
                'cost_price': Decimal('6800.00'),
                'sale_price': Decimal('8500.00'),
                'stock': 15,
                'min_stock': 5,
            },
        ]

        for p_data in sample_products:
            prod, created_prod = Product.objects.get_or_create(
                sku=p_data['sku'],
                defaults=p_data
            )
            if created_prod and prod.stock > 0:
                InventoryMovement.objects.create(
                    product=prod,
                    movement_type=InventoryMovement.MOVEMENT_IN,
                    quantity=prod.stock,
                    previous_stock=0,
                    new_stock=prod.stock,
                    reference='Stock inicial de apertura',
                    user=admin_user,
                    notes='Sembrado de catálogo inicial.'
                )
        self.stdout.write(self.style.SUCCESS('Productos y Kardex iniciales creados exitosamente.'))

        # 5. Crear Clientes de Demostración
        from customers.models import Customer
        sample_customers = [
            {
                'name': 'Consumidor Final',
                'document_id': '222222222222',
                'phone': '0000000000',
                'notes': 'Cliente genérico para ventas al contado'
            },
            {
                'name': 'Ana María Restrepo',
                'document_id': '1020304050',
                'phone': '3124567890',
                'email': 'ana.restrepo@correo.com',
                'address': 'Carrera 15 # 45-30 Apto 201',
                'notes': 'Cliente frecuente de barrio. Buen historial crediticio.'
            },
            {
                'name': 'Restaurante Sabor Criollo',
                'document_id': '900876543-1',
                'phone': '3209876543',
                'email': 'pedidos@saborcriollo.com',
                'address': 'Calle 72 # 11-40',
                'notes': 'Compras semanales en volumen para cocina.'
            }
        ]

        for c_data in sample_customers:
            Customer.objects.get_or_create(name=c_data['name'], defaults=c_data)
        self.stdout.write(self.style.SUCCESS('Clientes iniciales creados.'))

        # 6. Crear Proveedores de Demostración
        from suppliers.models import Supplier
        sample_suppliers = [
            {
                'name': 'Distribuidora Lácteos del Valle S.A.',
                'contact_name': 'Roberto Martínez',
                'tax_id': '890123456-1',
                'phone': '6013456789',
                'email': 'ventas@lacteosdelvalle.com',
                'address': 'Zona Industrial Calle 13',
                'notes': 'Días de entrega: Martes y Jueves. Plazo de pago: 15 días.'
            },
            {
                'name': 'Mayorista de Abarrotes Central',
                'contact_name': 'Claudia Pineda',
                'tax_id': '800987654-3',
                'phone': '3157654321',
                'email': 'pedidos@centralabarrotes.com',
                'address': 'Central Mayorista Bodega 4',
                'notes': 'Descuento del 3% por pago de contado.'
            }
        ]

        for s_data in sample_suppliers:
            Supplier.objects.get_or_create(name=s_data['name'], defaults=s_data)
        self.stdout.write(self.style.SUCCESS('Proveedores iniciales creados.'))
