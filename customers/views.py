from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Customer
from .forms import CustomerForm

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

    # Placeholder para deudas activas (se conectará en Fase 7)
    debts = []
    if hasattr(customer, 'debts'):
        debts = customer.debts.filter(is_paid=False)

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
