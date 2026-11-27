import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from .models import Supplier, Purchase, PurchaseItem, SupplierDebt, SupplierPayment
from .forms import SupplierForm, SupplierPaymentForm
from inventory.models import Product, InventoryMovement
from core.decorators import admin_required


# ==============================================================================
# GESTIÓN DE PROVEEDORES
# ==============================================================================

@login_required
@admin_required
def supplier_list(request):
    """
    Listado y búsqueda de proveedores comerciales.
    """
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')

    suppliers = Supplier.objects.all()

    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) |
            Q(contact_name__icontains=search) |
            Q(tax_id__icontains=search) |
            Q(phone__icontains=search)
        )

    if status_filter == 'active':
        suppliers = suppliers.filter(is_active=True)
    elif status_filter == 'inactive':
        suppliers = suppliers.filter(is_active=False)

    paginator = Paginator(suppliers, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Directorio de Proveedores',
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'total_count': suppliers.count(),
    }
    return render(request, 'suppliers/supplier_list.html', context)


@login_required
@admin_required
def supplier_create(request):
    """
    Registrar nuevo proveedor.
    """
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Proveedor "{supplier.name}" registrado correctamente.')
            return redirect('suppliers:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm()

    return render(request, 'suppliers/supplier_form.html', {
        'title': 'Registrar Nuevo Proveedor',
        'form': form,
        'action': 'Crear'
    })


@login_required
@admin_required
def supplier_update(request, pk):
    """
    Editar datos de un proveedor.
    """
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Proveedor "{supplier.name}" actualizado correctamente.')
            return redirect('suppliers:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)

    return render(request, 'suppliers/supplier_form.html', {
        'title': f'Editar Proveedor: {supplier.name}',
        'form': form,
        'supplier': supplier,
        'action': 'Actualizar'
    })


@login_required
@admin_required
def supplier_detail(request, pk):
    """
    Ficha de proveedor, historial de compras y deudas por pagar.
    """
    supplier = get_object_or_404(Supplier, pk=pk)
    purchases = supplier.purchases.all()[:10]

    debts = supplier.debts.select_related('purchase').filter(is_paid=False, is_cancelled=False)

    context = {
        'title': f'Ficha: {supplier.name}',
        'supplier': supplier,
        'purchases': purchases,
        'debts': debts,
    }
    return render(request, 'suppliers/supplier_detail.html', context)


@login_required
@admin_required
def supplier_toggle_active(request, pk):
    """
    Activar o desactivar proveedor.
    """
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.is_active = not supplier.is_active
    supplier.save(update_fields=['is_active'])

    estado = 'activado' if supplier.is_active else 'desactivado'
    messages.info(request, f'El proveedor "{supplier.name}" ha sido {estado}.')
    return redirect('suppliers:supplier_list')


# ==============================================================================
# GESTIÓN DE COMPRAS DE MERCANCÍA (FASE 6)
# ==============================================================================

@login_required
@admin_required
def purchase_list(request):
    """
    Historial general de compras de mercancía a proveedores.
    """
    search = request.GET.get('q', '').strip()
    supplier_id = request.GET.get('supplier', '')
    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')
    date_filter = request.GET.get('date', '')

    purchases = Purchase.objects.select_related('supplier', 'user').all()

    if search:
        purchases = purchases.filter(
            Q(invoice_number__icontains=search) |
            Q(supplier_invoice__icontains=search) |
            Q(supplier__name__icontains=search)
        )

    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)

    if status_filter:
        purchases = purchases.filter(status=status_filter)

    if method_filter:
        purchases = purchases.filter(payment_method=method_filter)

    if date_filter:
        purchases = purchases.filter(date__date=date_filter)

    total_amount = purchases.filter(status=Purchase.STATUS_COMPLETED).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    suppliers = Supplier.objects.filter(is_active=True)

    paginator = Paginator(purchases, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Historial de Compras de Mercancía',
        'page_obj': page_obj,
        'suppliers': suppliers,
        'search': search,
        'selected_supplier': supplier_id,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'date_filter': date_filter,
        'total_amount': total_amount,
        'total_count': purchases.count(),
    }
    return render(request, 'suppliers/purchase_list.html', context)


@login_required
@admin_required
def purchase_create(request):
    """
    Registro interactivo de una orden de compra con múltiples productos.
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                supplier_id = request.POST.get('supplier_id')
                supplier_invoice = request.POST.get('supplier_invoice', '').strip()
                payment_method = request.POST.get('payment_method', Purchase.PAYMENT_CASH)
                notes = request.POST.get('notes', '').strip()
                update_costs = request.POST.get('update_costs') == 'on'
                items_json = request.POST.get('items_json', '[]')

                items_data = json.loads(items_json)
                if not items_data:
                    messages.error(request, 'Debe incluir al menos un producto en la compra.')
                    return redirect('suppliers:purchase_create')

                supplier = get_object_or_404(Supplier, id=supplier_id, is_active=True)

                # Crear compra
                purchase = Purchase.objects.create(
                    invoice_number=Purchase.generate_next_invoice_number(),
                    supplier_invoice=supplier_invoice,
                    supplier=supplier,
                    user=request.user,
                    payment_method=payment_method,
                    notes=notes
                )

                subtotal_calc = Decimal('0.00')

                for item in items_data:
                    prod_id = item.get('product_id')
                    qty = int(item.get('quantity', 1))
                    unit_cost = Decimal(str(item.get('unit_cost', 0)))

                    if qty <= 0:
                        continue

                    product = Product.objects.select_for_update().get(id=prod_id)
                    item_subtotal = unit_cost * qty
                    subtotal_calc += item_subtotal

                    PurchaseItem.objects.create(
                        purchase=purchase,
                        product=product,
                        quantity=qty,
                        unit_cost=unit_cost,
                        subtotal=item_subtotal
                    )

                    # Incrementar existencias en el inventario con registro en Kardex
                    product.adjust_stock(
                        quantity=qty,
                        movement_type=InventoryMovement.MOVEMENT_IN,
                        reference=f"Compra Factura #{purchase.invoice_number}",
                        user=request.user,
                        notes=f"Proveedor: {supplier.name} (Factura Ref: {supplier_invoice or 'N/A'})"
                    )

                    # Actualizar costo unitario del producto si se solicitó
                    if update_costs and unit_cost > Decimal('0.00'):
                        product.cost_price = unit_cost
                        product.save(update_fields=['cost_price', 'updated_at'])

                purchase.subtotal = subtotal_calc
                purchase.total = subtotal_calc
                purchase.save(update_fields=['subtotal', 'total'])

                # Auto-crear cuenta por pagar para compras a crédito o pago parcial
                if payment_method in [Purchase.PAYMENT_CREDIT, Purchase.PAYMENT_PARTIAL]:
                    initial_payment = Decimal(str(request.POST.get('initial_payment', '0') or '0'))
                    if initial_payment < Decimal('0.00'):
                        initial_payment = Decimal('0.00')
                    if initial_payment > purchase.total:
                        raise ValueError('El abono inicial no puede ser mayor al total de la compra.')

                    debt = SupplierDebt.objects.create(
                        supplier=supplier,
                        purchase=purchase,
                        total_amount=purchase.total,
                        paid_amount=Decimal('0.00'),
                        pending_balance=purchase.total,
                    )
                    if payment_method == Purchase.PAYMENT_PARTIAL and initial_payment > Decimal('0.00'):
                        debt.register_payment(
                            amount=initial_payment,
                            payment_method=SupplierPayment.PAYMENT_CASH,
                            user=request.user,
                            notes=f'Abono inicial en Compra #{purchase.invoice_number}',
                        )

                # Registrar movimiento financiero solo si sale dinero de inmediato (contado/transferencia).
                if payment_method in [Purchase.PAYMENT_CASH, Purchase.PAYMENT_TRANSFER] and purchase.total > Decimal('0.00'):
                    from finance.models import FinancialCategory, FinancialMovement
                    category = FinancialCategory.get_or_create_system_category(
                        'Compra de Mercancía', FinancialCategory.TYPE_EXPENSE
                    )
                    fin_method = (
                        FinancialMovement.PAYMENT_TRANSFER
                        if payment_method == Purchase.PAYMENT_TRANSFER
                        else FinancialMovement.PAYMENT_CASH
                    )
                    FinancialMovement.objects.create(
                        movement_type=FinancialMovement.TYPE_EXPENSE,
                        category=category,
                        description=f"Compra #{purchase.invoice_number} - {supplier.name}",
                        amount=purchase.total,
                        payment_method=fin_method,
                        user=request.user,
                        purchase=purchase,
                    )

                messages.success(request, f'¡Compra #{purchase.invoice_number} registrada exitosamente por ${purchase.total:,.2f}!')
                return redirect('suppliers:purchase_detail', pk=purchase.pk)

        except Exception as e:
            messages.error(request, f'Error al registrar la compra: {str(e)}')
            return redirect('suppliers:purchase_create')

    suppliers = Supplier.objects.filter(is_active=True)
    products = Product.objects.all().select_related('category')

    products_catalog = [
        {
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'category': p.category.name,
            'cost_price': float(p.cost_price),
            'stock': p.stock,
        }
        for p in products
    ]

    context = {
        'title': 'Registrar Compra de Mercancía',
        'suppliers': suppliers,
        'products_catalog_json': json.dumps(products_catalog),
        'next_invoice': Purchase.generate_next_invoice_number(),
    }
    return render(request, 'suppliers/purchase_form.html', context)


@login_required
@admin_required
def purchase_detail(request, pk):
    """
    Detalle completo de una orden de compra.
    """
    purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'user'), pk=pk)
    items = purchase.items.select_related('product').all()

    context = {
        'title': f'Compra #{purchase.invoice_number}',
        'purchase': purchase,
        'items': items,
    }
    return render(request, 'suppliers/purchase_detail.html', context)


@login_required
@admin_required
def purchase_cancel(request, pk):
    """
    Anula una compra y descuenta del inventario las unidades ingresadas.
    """
    purchase = get_object_or_404(Purchase, pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '').strip()
        if not reason:
            messages.error(request, 'Debe especificar el motivo de anulación de la compra.')
            return redirect('suppliers:purchase_detail', pk=purchase.pk)

        try:
            purchase.cancel(user=request.user, reason=reason)
            messages.warning(request, f'La compra #{purchase.invoice_number} ha sido anulada y el stock fue debitado del inventario.')
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al anular la compra: {str(e)}')

    return redirect('suppliers:purchase_detail', pk=purchase.pk)


# ==============================================================================
# CUENTAS POR PAGAR (FASE 7)
# ==============================================================================

@login_required
@admin_required
def debt_list(request):
    """
    Listado de cuentas por pagar a proveedores con filtros.
    """
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'pending')

    debts = SupplierDebt.objects.select_related('supplier', 'purchase').filter(is_cancelled=False)

    if search:
        debts = debts.filter(
            Q(supplier__name__icontains=search) |
            Q(purchase__invoice_number__icontains=search)
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
        'title': 'Cuentas por Pagar',
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'total_pending': total_pending,
        'total_count': debts.count(),
    }
    return render(request, 'suppliers/debt_list.html', context)


@login_required
@admin_required
def debt_detail(request, pk):
    """
    Detalle de una cuenta por pagar e historial de pagos al proveedor.
    """
    debt = get_object_or_404(SupplierDebt.objects.select_related('supplier', 'purchase'), pk=pk)
    payments = debt.payments.select_related('user').all()
    form = SupplierPaymentForm()

    context = {
        'title': f'Cuenta por Pagar – {debt.supplier.name}',
        'debt': debt,
        'payments': payments,
        'form': form,
    }
    return render(request, 'suppliers/debt_detail.html', context)


@login_required
@admin_required
def debt_register_payment(request, pk):
    """
    Registra un pago o abono a un proveedor.
    """
    debt = get_object_or_404(SupplierDebt, pk=pk)

    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            try:
                debt.register_payment(
                    amount=form.cleaned_data['amount'],
                    payment_method=form.cleaned_data['payment_method'],
                    user=request.user,
                    reference=form.cleaned_data.get('reference', ''),
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f'Pago de ${form.cleaned_data["amount"]:,.2f} registrado correctamente.')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        messages.error(request, 'Método no permitido.')

    return redirect('suppliers:debt_detail', pk=debt.pk)
