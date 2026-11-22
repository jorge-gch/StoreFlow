import json
from decimal import Decimal
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count

from .forms import LoginForm, UserProfileForm
from .models import UserProfile


def login_view(request):
    """
    Vista de autenticación de usuarios.
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                user_name = user.get_full_name() or user.username
                role_display = user.profile.get_role_display() if hasattr(user, 'profile') else 'Usuario'
                messages.success(request, f'¡Bienvenido/a {user_name}! Has ingresado como {role_display}.')
                
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('core:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos. Por favor, intente de nuevo.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    """
    Cierre de sesión de usuarios.
    """
    logout(request)
    messages.info(request, 'Ha cerrado sesión correctamente.')
    return redirect('core:login')


@login_required
def dashboard_view(request):
    """
    Panel de control principal del sistema StoreFlow.
    Muestra KPIs en tiempo real, gráficas financieras y resúmenes operativos.
    """
    today = timezone.localdate()
    start_of_month = today.replace(day=1)

    # Indicadores por defecto (se conectarán dinámicamente con los modelos en las Fases 3 a 8)
    metrics = {
        'sales_today': Decimal('0.00'),
        'income_month': Decimal('0.00'),
        'expenses_month': Decimal('0.00'),
        'estimated_profit': Decimal('0.00'),
        'total_products': 0,
        'low_stock_count': 0,
        'pending_receivables': Decimal('0.00'),
        'pending_payables': Decimal('0.00'),
    }

    low_stock_products = []
    # Intentar obtener métricas de Inventory si el modelo existe
    try:
        from inventory.models import Product
        metrics['total_products'] = Product.objects.filter(is_active=True).count()
        metrics['low_stock_count'] = Product.objects.filter(is_active=True, stock__lte=F('min_stock')).count()
        low_stock_products = list(Product.objects.filter(is_active=True, stock__lte=F('min_stock'))[:5])
    except Exception:
        pass

    # Intentar obtener métricas de Sales si el modelo existe
    try:
        from sales.models import Sale
        sales_today_qs = Sale.objects.filter(date__date=today, status='completed')
        metrics['sales_today'] = sales_today_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    except Exception:
        pass

    # Intentar obtener métricas financieras si el modelo existe
    try:
        from finance.models import FinancialMovement
        income_qs = FinancialMovement.objects.filter(movement_type='income', date__gte=start_of_month)
        expenses_qs = FinancialMovement.objects.filter(movement_type='expense', date__gte=start_of_month)
        
        metrics['income_month'] = income_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        metrics['expenses_month'] = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        metrics['estimated_profit'] = metrics['income_month'] - metrics['expenses_month']
    except Exception:
        pass

    # Intentar obtener cuentas por cobrar si el modelo existe
    try:
        from customers.models import CustomerDebt
        metrics['pending_receivables'] = CustomerDebt.objects.filter(is_paid=False).aggregate(total=Sum('pending_balance'))['total'] or Decimal('0.00')
    except Exception:
        pass

    # Intentar obtener cuentas por pagar si el modelo existe
    try:
        from suppliers.models import SupplierDebt
        metrics['pending_payables'] = SupplierDebt.objects.filter(is_paid=False).aggregate(total=Sum('pending_balance'))['total'] or Decimal('0.00')
    except Exception:
        pass

    # Generar etiquetas de los últimos 6 meses para la gráfica
    months_labels = []
    income_data = [0, 0, 0, 0, 0, 0]
    expenses_data = [0, 0, 0, 0, 0, 0]

    month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    current_month = today.month
    for i in range(5, -1, -1):
        m = (current_month - i - 1) % 12 + 1
        months_labels.append(month_names[m - 1])

    recent_sales = []

    context = {
        'title': 'Dashboard Principal',
        'metrics': metrics,
        'recent_sales': recent_sales,
        'low_stock_products': low_stock_products,
        'months_labels_json': json.dumps(months_labels),
        'income_data_json': json.dumps(income_data),
        'expenses_data_json': json.dumps(expenses_data),
    }

    return render(request, 'core/dashboard.html', context)


@login_required
def profile_view(request):
    """
    Vista para consultar y actualizar el perfil del usuario activo.
    """
    profile = request.user.profile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu información de perfil ha sido actualizada exitosamente.')
            return redirect('core:profile')
    else:
        form = UserProfileForm(instance=profile)

    context = {
        'title': 'Mi Perfil',
        'form': form,
        'profile': profile,
    }
    return render(request, 'core/profile.html', context)
