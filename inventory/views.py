from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.urls import reverse

from .models import Product, Category, InventoryMovement
from .forms import ProductForm, CategoryForm, ManualStockMovementForm
from core.decorators import admin_required

@login_required
def product_list(request):
    """
    Listado general de productos con búsqueda, filtros y alertas de stock bajo.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    stock_filter = request.GET.get('stock_status', '')

    products = Product.objects.select_related('category').all()

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(sku__icontains=search_query)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if stock_filter == 'low':
        products = products.filter(stock__lte=F('min_stock'))
    elif stock_filter == 'out':
        products = products.filter(stock=0)
    elif stock_filter == 'inactive':
        products = products.filter(is_active=False)
    else:
        products = products.filter(is_active=True)

    categories = Category.objects.filter(is_active=True)

    paginator = Paginator(products, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Inventario de Productos',
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'stock_filter': stock_filter,
        'total_count': products.count(),
    }
    return render(request, 'inventory/product_list.html', context)


@login_required
@admin_required
def product_create(request):
    """
    Registro de nuevos productos en inventario.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            # Si se especificó un stock inicial mayor a 0, registrar en Kardex
            if product.stock > 0:
                InventoryMovement.objects.create(
                    product=product,
                    movement_type=InventoryMovement.MOVEMENT_IN,
                    quantity=product.stock,
                    previous_stock=0,
                    new_stock=product.stock,
                    reference='Stock inicial de apertura',
                    user=request.user,
                    notes='Registro inicial al crear producto.'
                )
            messages.success(request, f'Producto "{product.name}" registrado correctamente.')
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = ProductForm()

    return render(request, 'inventory/product_form.html', {
        'title': 'Registrar Nuevo Producto',
        'form': form,
        'action': 'Crear'
    })


@login_required
@admin_required
def product_update(request, pk):
    """
    Edición de información de un producto.
    """
    product = get_object_or_404(Product, pk=pk)
    previous_stock = product.stock

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            updated_product = form.save()
            # Si el stock fue cambiado directamente desde el formulario
            if updated_product.stock != previous_stock:
                diff = updated_product.stock - previous_stock
                m_type = InventoryMovement.MOVEMENT_IN if diff > 0 else InventoryMovement.MOVEMENT_OUT
                InventoryMovement.objects.create(
                    product=updated_product,
                    movement_type=m_type,
                    quantity=abs(diff),
                    previous_stock=previous_stock,
                    new_stock=updated_product.stock,
                    reference='Ajuste directo desde edición de producto',
                    user=request.user
                )
            messages.success(request, f'Producto "{updated_product.name}" actualizado correctamente.')
            return redirect('inventory:product_detail', pk=updated_product.pk)
    else:
        form = ProductForm(instance=product)

    return render(request, 'inventory/product_form.html', {
        'title': f'Editar Producto: {product.name}',
        'form': form,
        'product': product,
        'action': 'Actualizar'
    })


@login_required
def product_detail(request, pk):
    """
    Ficha técnica del producto y sus últimos movimientos de kardex.
    """
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    recent_movements = product.movements.select_related('user').all()[:10]
    movement_form = ManualStockMovementForm()

    context = {
        'title': f'Detalle: {product.name}',
        'product': product,
        'recent_movements': recent_movements,
        'movement_form': movement_form,
    }
    return render(request, 'inventory/product_detail.html', context)


@login_required
@admin_required
def product_toggle_active(request, pk):
    """
    Desactiva o activa un producto (baja lógica).
    """
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    
    estado = 'activado' if product.is_active else 'desactivado'
    messages.info(request, f'El producto "{product.name}" ha sido {estado}.')
    return redirect('inventory:product_list')


@login_required
@admin_required
def product_adjust_stock(request, pk):
    """
    Procesa un movimiento manual de stock (entrada, salida o ajuste).
    """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ManualStockMovementForm(request.POST)
        if form.is_valid():
            movement_type = form.cleaned_data['movement_type']
            quantity = form.cleaned_data['quantity']
            reference = form.cleaned_data['reference']
            notes = form.cleaned_data['notes']

            try:
                product.adjust_stock(
                    quantity=quantity,
                    movement_type=movement_type,
                    reference=reference,
                    user=request.user,
                    notes=notes
                )
                messages.success(request, f'Movimiento registrado con éxito. Nuevo stock: {product.stock} unidades.')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'Por favor revise los campos del formulario de ajuste.')

    return redirect('inventory:product_detail', pk=product.pk)


@login_required
def movement_list(request):
    """
    Historial completo de movimientos de inventario (Kardex general).
    """
    search = request.GET.get('q', '').strip()
    m_type = request.GET.get('type', '')

    movements = InventoryMovement.objects.select_related('product', 'user').all()

    if search:
        movements = movements.filter(
            Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(reference__icontains=search)
        )

    if m_type:
        movements = movements.filter(movement_type=m_type)

    paginator = Paginator(movements, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Kardex - Movimientos de Inventario',
        'page_obj': page_obj,
        'search': search,
        'm_type': m_type,
    }
    return render(request, 'inventory/movement_list.html', context)


@login_required
def category_list(request):
    """
    Listado y gestión de categorías.
    """
    categories = Category.objects.all()
    form = CategoryForm()

    if request.method == 'POST' and request.user.profile.is_admin:
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Categoría "{category.name}" creada exitosamente.')
            return redirect('inventory:category_list')

    context = {
        'title': 'Categorías de Productos',
        'categories': categories,
        'form': form,
    }
    return render(request, 'inventory/category_list.html', context)


@login_required
@admin_required
def category_update(request, pk):
    """
    Edición de una categoría.
    """
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{category.name}" actualizada con éxito.')
            return redirect('inventory:category_list')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'inventory/category_form.html', {
        'title': f'Editar Categoría: {category.name}',
        'form': form,
        'category': category,
    })
