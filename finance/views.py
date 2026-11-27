from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from core.decorators import admin_required
from .models import FinancialCategory, FinancialMovement
from .forms import FinancialCategoryForm, FinancialMovementForm


def _ensure_default_categories():
    """Garantiza que existan las categorías financieras base de la tienda."""
    defaults = [
        ('Ventas de Contado', FinancialCategory.TYPE_INCOME, True),
        ('Abonos de Clientes', FinancialCategory.TYPE_INCOME, True),
        ('Otros Ingresos', FinancialCategory.TYPE_INCOME, False),
        ('Compra de Mercancía', FinancialCategory.TYPE_EXPENSE, True),
        ('Pagos a Proveedores', FinancialCategory.TYPE_EXPENSE, True),
        ('Pago de Servicios', FinancialCategory.TYPE_EXPENSE, False),
        ('Arriendo', FinancialCategory.TYPE_EXPENSE, False),
        ('Transporte', FinancialCategory.TYPE_EXPENSE, False),
        ('Nómina', FinancialCategory.TYPE_EXPENSE, False),
        ('Otros Gastos', FinancialCategory.TYPE_EXPENSE, False),
    ]
    for name, m_type, is_sys in defaults:
        FinancialCategory.objects.get_or_create(
            name=name,
            movement_type=m_type,
            defaults={'is_system': is_sys, 'is_active': True}
        )


@login_required
@admin_required
def movement_list(request):
    """
    Listado general de ingresos y egresos con filtros y totales del período.
    """
    _ensure_default_categories()

    search = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    method_filter = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    show_cancelled = request.GET.get('cancelled', '') == '1'

    movements = FinancialMovement.objects.select_related('category', 'user').all()
    if not show_cancelled:
        movements = movements.filter(is_cancelled=False)

    if search:
        movements = movements.filter(
            Q(description__icontains=search) |
            Q(notes__icontains=search) |
            Q(category__name__icontains=search)
        )
    if type_filter:
        movements = movements.filter(movement_type=type_filter)
    if category_id:
        movements = movements.filter(category_id=category_id)
    if method_filter:
        movements = movements.filter(payment_method=method_filter)
    if date_from:
        movements = movements.filter(date__date__gte=date_from)
    if date_to:
        movements = movements.filter(date__date__lte=date_to)

    active_qs = movements.filter(is_cancelled=False)
    total_income = active_qs.filter(
        movement_type=FinancialMovement.TYPE_INCOME
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense = active_qs.filter(
        movement_type=FinancialMovement.TYPE_EXPENSE
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_balance = total_income - total_expense

    paginator = Paginator(movements, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = FinancialCategory.objects.filter(is_active=True)

    context = {
        'title': 'Ingresos y Egresos',
        'page_obj': page_obj,
        'categories': categories,
        'search': search,
        'type_filter': type_filter,
        'category_id': category_id,
        'method_filter': method_filter,
        'date_from': date_from,
        'date_to': date_to,
        'show_cancelled': show_cancelled,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_balance': net_balance,
    }
    return render(request, 'finance/movement_list.html', context)


@login_required
@admin_required
def movement_create(request):
    """
    Registrar un ingreso o egreso manual.
    """
    _ensure_default_categories()

    if request.method == 'POST':
        form = FinancialMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.user = request.user
            movement.save()
            messages.success(
                request,
                f'{movement.get_movement_type_display()} de ${movement.amount:,.2f} registrado correctamente.'
            )
            return redirect('finance:movement_list')
    else:
        initial_type = request.GET.get('type', FinancialMovement.TYPE_EXPENSE)
        form = FinancialMovementForm(initial={'movement_type': initial_type})

    categories = list(
        FinancialCategory.objects.filter(is_active=True).values('id', 'name', 'movement_type')
    )

    return render(request, 'finance/movement_form.html', {
        'title': 'Registrar Movimiento Financiero',
        'form': form,
        'categories': categories,
    })


@login_required
@admin_required
def movement_cancel(request, pk):
    """
    Anula un movimiento financiero manual sin eliminar el registro histórico.
    """
    movement = get_object_or_404(FinancialMovement, pk=pk)

    if request.method == 'POST':
        if movement.is_automatic:
            messages.error(
                request,
                'Este movimiento proviene de una venta, compra o abono. Debe anular el documento de origen.'
            )
        elif movement.is_cancelled:
            messages.info(request, 'Este movimiento ya se encuentra anulado.')
        else:
            movement.is_cancelled = True
            movement.save(update_fields=['is_cancelled'])
            messages.warning(request, f'Movimiento "{movement.description}" anulado correctamente.')

    return redirect('finance:movement_list')


@login_required
@admin_required
def category_list(request):
    """
    Listado y gestión de categorías financieras.
    """
    _ensure_default_categories()
    categories = FinancialCategory.objects.all()
    return render(request, 'finance/category_list.html', {
        'title': 'Categorías Financieras',
        'categories': categories,
    })


@login_required
@admin_required
def category_create(request):
    """
    Crear nueva categoría financiera.
    """
    if request.method == 'POST':
        form = FinancialCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'Categoría "{cat.name}" creada correctamente.')
            return redirect('finance:category_list')
    else:
        form = FinancialCategoryForm()

    return render(request, 'finance/category_form.html', {
        'title': 'Nueva Categoría Financiera',
        'form': form,
        'action': 'Crear',
    })


@login_required
@admin_required
def category_update(request, pk):
    """
    Editar categoría financiera.
    """
    category = get_object_or_404(FinancialCategory, pk=pk)
    if request.method == 'POST':
        form = FinancialCategoryForm(request.POST, instance=category)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'Categoría "{cat.name}" actualizada.')
            return redirect('finance:category_list')
    else:
        form = FinancialCategoryForm(instance=category)

    return render(request, 'finance/category_form.html', {
        'title': f'Editar Categoría: {category.name}',
        'form': form,
        'action': 'Actualizar',
    })
