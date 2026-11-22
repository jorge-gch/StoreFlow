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
