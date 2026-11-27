from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone

from sales.models import Sale, SaleItem
from inventory.models import Product, InventoryMovement
from customers.models import CustomerDebt
from suppliers.models import SupplierDebt
from finance.models import FinancialMovement


def build_report_dataset(report_type, date_from, date_to):
    """
    Construye (titulo, encabezados, filas) para los diferentes reportes exportables.
    """
    if report_type == 'sales':
        qs = Sale.objects.select_related('customer', 'user').filter(
            status=Sale.STATUS_COMPLETED,
            date__date__gte=date_from,
            date__date__lte=date_to,
        )
        headers = ['Factura', 'Fecha', 'Cliente', 'Método Pago', 'Vendedor', 'Descuento', 'Total']
        rows = [
            [
                s.invoice_number,
                timezone.localtime(s.date).strftime('%d/%m/%Y %H:%M'),
                s.customer.name if s.customer else 'Consumidor Final',
                s.get_payment_method_display(),
                s.user.username,
                f"${s.discount:,.2f}",
                f"${s.total:,.2f}",
            ]
            for s in qs
        ]
        return 'Reporte de Ventas', headers, rows

    if report_type == 'top_products':
        qs = (
            SaleItem.objects.filter(
                sale__status=Sale.STATUS_COMPLETED,
                sale__date__date__gte=date_from,
                sale__date__date__lte=date_to,
            )
            .values('product__sku', 'product__name', 'product__category__name')
            .annotate(units=Sum('quantity'), revenue=Sum('subtotal'))
            .order_by('-units')
        )
        headers = ['SKU', 'Producto', 'Categoría', 'Unidades Vendidas', 'Ingresos Generados']
        rows = [
            [
                item['product__sku'],
                item['product__name'],
                item['product__category__name'],
                item['units'],
                f"${item['revenue']:,.2f}",
            ]
            for item in qs
        ]
        return 'Productos Más Vendidos', headers, rows

    if report_type == 'low_rotation':
        sold_map = {
            item['product_id']: item['units']
            for item in SaleItem.objects.filter(
                sale__status=Sale.STATUS_COMPLETED,
                sale__date__date__gte=date_from,
                sale__date__date__lte=date_to,
            )
            .values('product_id')
            .annotate(units=Sum('quantity'))
        }
        products = Product.objects.select_related('category').filter(is_active=True)
        enriched = sorted(
            [(p, sold_map.get(p.id, 0)) for p in products],
            key=lambda pair: (pair[1], -pair[0].stock),
        )
        headers = ['SKU', 'Producto', 'Categoría', 'Stock Actual', 'Unidades Vendidas']
        rows = [
            [p.sku, p.name, p.category.name, p.stock, units]
            for p, units in enriched
        ]
        return 'Productos con Menor Rotación', headers, rows

    if report_type == 'finance':
        qs = FinancialMovement.objects.select_related('category', 'user').filter(
            is_cancelled=False,
            date__date__gte=date_from,
            date__date__lte=date_to,
        )
        headers = ['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Método', 'Usuario', 'Valor']
        rows = [
            [
                timezone.localtime(m.date).strftime('%d/%m/%Y %H:%M'),
                m.get_movement_type_display(),
                m.category.name,
                m.description,
                m.get_payment_method_display(),
                m.user.username,
                f"${m.amount:,.2f}",
            ]
            for m in qs
        ]
        return 'Ingresos y Egresos', headers, rows

    if report_type == 'receivables':
        qs = CustomerDebt.objects.select_related('customer', 'sale').filter(
            is_paid=False, is_cancelled=False
        )
        headers = ['Cliente', 'Teléfono', 'Factura', 'Total', 'Abonado', 'Saldo Pendiente', 'Estado']
        rows = [
            [
                d.customer.name,
                d.customer.phone,
                d.sale.invoice_number,
                f"${d.total_amount:,.2f}",
                f"${d.paid_amount:,.2f}",
                f"${d.pending_balance:,.2f}",
                'Vencida' if d.is_overdue else 'Pendiente',
            ]
            for d in qs
        ]
        return 'Cuentas por Cobrar', headers, rows

    if report_type == 'payables':
        qs = SupplierDebt.objects.select_related('supplier', 'purchase').filter(
            is_paid=False, is_cancelled=False
        )
        headers = ['Proveedor', 'Teléfono', 'Compra', 'Total', 'Pagado', 'Saldo Pendiente', 'Estado']
        rows = [
            [
                d.supplier.name,
                d.supplier.phone,
                d.purchase.invoice_number,
                f"${d.total_amount:,.2f}",
                f"${d.paid_amount:,.2f}",
                f"${d.pending_balance:,.2f}",
                'Vencida' if d.is_overdue else 'Pendiente',
            ]
            for d in qs
        ]
        return 'Cuentas por Pagar', headers, rows

    if report_type == 'inventory_movements':
        qs = InventoryMovement.objects.select_related('product', 'user').filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        headers = ['Fecha', 'Producto', 'Tipo', 'Cantidad', 'Stock Ant.', 'Stock Nuevo', 'Referencia', 'Usuario']
        rows = [
            [
                timezone.localtime(m.created_at).strftime('%d/%m/%Y %H:%M'),
                m.product.name,
                m.get_movement_type_display(),
                m.quantity,
                m.previous_stock,
                m.new_stock,
                m.reference,
                m.user.username if m.user else 'Sistema',
            ]
            for m in qs
        ]
        return 'Movimientos de Inventario', headers, rows

    raise ValueError(f'Tipo de reporte no soportado: {report_type}')
