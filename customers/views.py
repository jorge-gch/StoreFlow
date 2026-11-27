from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from .models import Customer, CustomerDebt, CustomerPayment
from .forms import CustomerForm, CustomerPaymentForm

@login_required
def customer_list(request):
    """
    Listado y búsqueda de clientes.
    """
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')

    customers = Customer.objects.all()

    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(document_id__icontains=search) |
            Q(phone__icontains=search)
        )

    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'inactive':
        customers = customers.filter(is_active=False)

    paginator = Paginator(customers, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Directorio de Clientes',
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'total_count': customers.count(),
    }
    return render(request, 'customers/customer_list.html', context)


@login_required
def customer_create(request):
    """
    Registrar nuevo cliente.
    """
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Cliente "{customer.name}" registrado exitosamente.')
            return redirect('customers:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'customers/customer_form.html', {
        'title': 'Registrar Nuevo Cliente',
        'form': form,
        'action': 'Crear'
    })


@login_required
def customer_update(request, pk):
    """
    Editar datos del cliente.
    """
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Cliente "{customer.name}" actualizado correctamente.')
            return redirect('customers:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/customer_form.html', {
        'title': f'Editar Cliente: {customer.name}',
        'form': form,
        'customer': customer,
        'action': 'Actualizar'
    })


@login_required
def customer_detail(request, pk):
    """
    Ficha de cliente con resumen de compras y créditos.
    """
    customer = get_object_or_404(Customer, pk=pk)
    
    # Placeholder para historial de compras (se conectará en Fase 5)
    purchases = []
    if hasattr(customer, 'sales'):
        purchases = customer.sales.all()[:10]

    # Deudas activas
    debts = customer.debts.select_related('sale').filter(is_paid=False, is_cancelled=False)

    context = {
        'title': f'Ficha de Cliente: {customer.name}',
        'customer': customer,
        'purchases': purchases,
        'debts': debts,
    }
    return render(request, 'customers/customer_detail.html', context)


@login_required
def customer_toggle_active(request, pk):
    """
    Activar o desactivar cliente.
    """
    customer = get_object_or_404(Customer, pk=pk)
    customer.is_active = not customer.is_active
    customer.save(update_fields=['is_active'])

    estado = 'activado' if customer.is_active else 'desactivado'
    messages.info(request, f'El cliente "{customer.name}" ha sido {estado}.')
    return redirect('customers:customer_list')


# ==============================================================================
# CUENTAS POR COBRAR (FASE 7)
# ==============================================================================

@login_required
def debt_list(request):
    """
    Listado de cuentas por cobrar con filtros por cliente/factura y estado.
    """
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'pending')

    debts = CustomerDebt.objects.select_related('customer', 'sale').filter(is_cancelled=False)

    if search:
        debts = debts.filter(
            Q(customer__name__icontains=search) |
            Q(sale__invoice_number__icontains=search)
        )

    if status_filter == 'pending':
        debts = debts.filter(is_paid=False)
    elif status_filter == 'paid':
        debts = debts.filter(is_paid=True)

    total_pending = debts.filter(is_paid=False).aggregate(
        total=Sum('pending_balance')
    )['total'] or Decimal('0.00')

    paginator = Paginator(debts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'title': 'Cuentas por Cobrar',
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'total_pending': total_pending,
        'total_count': debts.count(),
    }
    return render(request, 'customers/debt_list.html', context)


@login_required
def debt_detail(request, pk):
    """
    Detalle de una cuenta por cobrar e historial de abonos.
    """
    debt = get_object_or_404(CustomerDebt.objects.select_related('customer', 'sale'), pk=pk)
    payments = debt.payments.select_related('user').all()
    form = CustomerPaymentForm()

    context = {
        'title': f'Cuenta por Cobrar – {debt.customer.name}',
        'debt': debt,
        'payments': payments,
        'form': form,
    }
    return render(request, 'customers/debt_detail.html', context)


@login_required
def debt_register_payment(request, pk):
    """
    Registra un abono a una cuenta por cobrar.
    """
    debt = get_object_or_404(CustomerDebt, pk=pk)

    if request.method == 'POST':
        form = CustomerPaymentForm(request.POST)
        if form.is_valid():
            try:
                debt.register_payment(
                    amount=form.cleaned_data['amount'],
                    payment_method=form.cleaned_data['payment_method'],
                    user=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f'Abono de ${form.cleaned_data["amount"]:,.2f} registrado correctamente.')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        messages.error(request, 'Método no permitido.')

    return redirect('customers:debt_detail', pk=debt.pk)
