import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from .models import Sale, SaleItem
from inventory.models import Product, InventoryMovement
from customers.models import Customer
from core.decorators import admin_required


@login_required
def pos_view(request):
    """
    Punto de Venta (POS) interactivo para registrar ventas con múltiples productos.
    """
    if request.method == 'POST':
        # Procesar venta
        try:
            with transaction.atomic():
                customer_id = request.POST.get('customer_id')
                payment_method = request.POST.get('payment_method', Sale.PAYMENT_CASH)
                discount_raw = request.POST.get('discount', '0')
                notes = request.POST.get('notes', '').strip()
                items_json = request.POST.get('items_json', '[]')

                items_data = json.loads(items_json)
                if not items_data:
                    messages.error(request, 'Debe agregar al menos un producto a la venta.')
                    return redirect('sales:pos')

                discount = Decimal(str(discount_raw or 0))
                if discount < Decimal('0.00'):
                    discount = Decimal('0.00')

                customer = None
                if customer_id:
                    customer = Customer.objects.filter(id=customer_id, is_active=True).first()

                # Crear cabecera de venta
                sale = Sale.objects.create(
                    invoice_number=Sale.generate_next_invoice_number(),
                    customer=customer,
                    user=request.user,
                    payment_method=payment_method,
                    discount=discount,
                    notes=notes
                )

                subtotal_calc = Decimal('0.00')

                # Procesar cada artículo del carrito
                for item in items_data:
                    prod_id = item.get('product_id')
                    qty = int(item.get('quantity', 1))
                    
                    if qty <= 0:
                        continue

                    # Bloquear producto para actualización concurrente
                    product = Product.objects.select_for_update().get(id=prod_id, is_active=True)

                    if product.stock < qty:
                        raise ValueError(f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}, solicitado: {qty}")

                    unit_price = product.sale_price
                    item_subtotal = unit_price * qty
                    subtotal_calc += item_subtotal

                    SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        quantity=qty,
                        unit_price=unit_price,
                        subtotal=item_subtotal
                    )

                    # Descontar del inventario y registrar en Kardex
                    product.adjust_stock(
                        quantity=qty,
                        movement_type=InventoryMovement.MOVEMENT_OUT,
                        reference=f"Venta Factura #{sale.invoice_number}",
                        user=request.user,
                        notes=f"Cliente: {customer.name if customer else 'Consumidor Final'}"
                    )

                # Calcular total final
                sale.subtotal = subtotal_calc
                sale.total = max(Decimal('0.00'), subtotal_calc - discount)
                sale.save(update_fields=['subtotal', 'total'])

                messages.success(request, f'¡Venta #{sale.invoice_number} registrada exitosamente por ${sale.total:,.2f}!')
                return redirect('sales:sale_detail', pk=sale.pk)

        except ValueError as ve:
            messages.error(request, str(ve))
            return redirect('sales:pos')
        except Exception as e:
            messages.error(request, f'Error al procesar la venta: {str(e)}')
            return redirect('sales:pos')

    # Vista GET: preparar catálogo y clientes para el POS
    products = Product.objects.filter(is_active=True, stock__gt=0).select_related('category')
    customers = Customer.objects.filter(is_active=True)

    # Serializar productos para búsqueda reactiva en frontend
    products_catalog = [
        {
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'category': p.category.name,
            'price': float(p.sale_price),
            'stock': p.stock,
        }
        for p in products
    ]

    context = {
        'title': 'Punto de Venta (POS)',
        'customers': customers,
        'products_catalog_json': json.dumps(products_catalog),
        'next_invoice': Sale.generate_next_invoice_number(),
    }
    return render(request, 'sales/pos.html', context)


@login_required
def sale_list(request):
    """
    Historial general de ventas con filtros de fecha, cliente, método de pago y estado.
    """
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    method_filter = request.GET.get('method', '')
    date_filter = request.GET.get('date', '')

    sales = Sale.objects.select_related('customer', 'user').all()

    if search:
        sales = sales.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(user__username__icontains=search)
        )

    if status_filter:
        sales = sales.filter(status=status_filter)

    if method_filter:
        sales = sales.filter(payment_method=method_filter)

    if date_filter:
        sales = sales.filter(date__date=date_filter)

    # Totales del conjunto filtrado
    total_amount = sales.filter(status=Sale.STATUS_COMPLETED).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Historial de Ventas',
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'date_filter': date_filter,
        'total_amount': total_amount,
        'total_count': sales.count(),
    }
    return render(request, 'sales/sale_list.html', context)


@login_required
def sale_detail(request, pk):
    """
    Consulta detallada de una factura o recibo de venta.
    """
    sale = get_object_or_404(Sale.objects.select_related('customer', 'user'), pk=pk)
    items = sale.items.select_related('product').all()

    context = {
        'title': f'Factura #{sale.invoice_number}',
        'sale': sale,
        'items': items,
    }
    return render(request, 'sales/sale_detail.html', context)


@login_required
@admin_required
def sale_cancel(request, pk):
    """
    Anula una venta y devuelve automáticamente los productos al inventario.
    """
    sale = get_object_or_404(Sale, pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '').strip()
        if not reason:
            messages.error(request, 'Debe especificar el motivo de anulación de la venta.')
            return redirect('sales:sale_detail', pk=sale.pk)

        try:
            sale.cancel(user=request.user, reason=reason)
            messages.warning(request, f'La venta #{sale.invoice_number} ha sido anulada y las unidades fueron reincorporadas al inventario.')
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al anular la venta: {str(e)}')

    return redirect('sales:sale_detail', pk=sale.pk)
