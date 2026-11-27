import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from inventory.models import Category, Product
from customers.models import Customer
from sales.models import Sale


class ReportsModuleTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_user(username='admin_rep', password='Password123!')
        self.admin.profile.role = UserProfile.ROLE_ADMIN
        self.admin.profile.save()

        self.employee = User.objects.create_user(username='emp_rep', password='Password123!')
        self.employee.profile.role = UserProfile.ROLE_EMPLOYEE
        self.employee.profile.save()

        self.customer = Customer.objects.create(name='Cliente Reportes', phone='3007778899')
        self.category = Category.objects.create(name='Tecnología')
        self.product = Product.objects.create(
            name='Mouse USB',
            sku='TEC-001',
            category=self.category,
            cost_price=Decimal('15000.00'),
            sale_price=Decimal('30000.00'),
            stock=20,
            min_stock=5,
        )

        # Crear venta vía POS para poblar ventas, finanzas e inventario
        self.client.login(username='admin_rep', password='Password123!')
        self.client.post(reverse('sales:pos'), {
            'customer_id': self.customer.id,
            'payment_method': Sale.PAYMENT_CASH,
            'discount': '0',
            'items_json': json.dumps([{'product_id': self.product.id, 'quantity': 2}]),
        })
        self.client.logout()

    def test_employee_cannot_access_reports(self):
        self.client.login(username='emp_rep', password='Password123!')
        res = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(res.status_code, 302)

    def test_admin_reports_dashboard_and_presets(self):
        self.client.login(username='admin_rep', password='Password123!')
        for preset in ['day', 'week', 'month']:
            res = self.client.get(reverse('reports:dashboard'), {'preset': preset})
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'Mouse USB')

    def test_export_reports_to_excel_and_pdf(self):
        self.client.login(username='admin_rep', password='Password123!')
        for report_type in ['sales', 'top_products', 'low_rotation', 'finance', 'receivables', 'payables', 'inventory_movements']:
            res_xlsx = self.client.get(reverse('reports:export_excel'), {'report': report_type})
            self.assertEqual(res_xlsx.status_code, 200)
            self.assertEqual(
                res_xlsx['Content-Type'],
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            self.assertGreater(len(res_xlsx.content), 100)

            res_pdf = self.client.get(reverse('reports:export_pdf'), {'report': report_type})
            self.assertEqual(res_pdf.status_code, 200)
            self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
            self.assertTrue(res_pdf.content.startswith(b'%PDF'))

    def test_dashboard_chart_reflects_real_income(self):
        self.client.login(username='admin_rep', password='Password123!')
        res = self.client.get(reverse('core:dashboard'))
        self.assertEqual(res.status_code, 200)
        income_data = json.loads(res.context['income_data_json'])
        self.assertEqual(income_data[-1], 60000.0)
