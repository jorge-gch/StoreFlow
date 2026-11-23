from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from customers.models import Customer

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
