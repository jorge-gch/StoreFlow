import json
from datetime import date, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone

from core.decorators import admin_required
from sales.models import Sale, SaleItem
from inventory.models import Product, InventoryMovement
from customers.models import CustomerDebt
from suppliers.models import SupplierDebt
from finance.models import FinancialMovement
from .exporters import export_to_excel, export_to_pdf
from .services import build_report_dataset


def _parse_date_range(request):
    """
    Obtiene el rango de fechas desde GET (?preset=day|week|month o ?date_from=...&date_to=...).
    Por defecto usa el mes actual.
    """
    today = timezone.localdate()
    preset = request.GET.get('preset', '')

    if preset == 'day':
        return today, today, 'day'
    if preset == 'week':
        return today - timedelta(days=6), today, 'week'
    if preset == 'month':
        return today.replace(day=1), today, 'month'

    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    try:
        date_from = date.fromisoformat(date_from_str) if date_from_str else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)

    try:
        date_to = date.fromisoformat(date_to_str) if date_to_str else today
    except ValueError:
        date_to = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    return date_from, date_to, ''


@login_required
@admin_required
def report_dashboard(request):
    """
    Centro de reportes y analítica del negocio con filtros por fecha y exportación Excel/PDF.
    """
    date_from, date_to, preset = _parse_date_range(request)

    # 1. Ventas del período
    sales_qs = Sale.objects.select_related('customer', 'user').filter(
        status=Sale.STATUS_COMPLETED,
        date__date__gte=date_from,
        date__date__lte=date_to,
    )
    sales_summary = sales_qs.aggregate(
        total=Sum('total'),
        count=Count('id'),
        discounts=Sum('discount'),
    )
    sales_total = sales_summary['total'] or Decimal('0.00')
    sales_count = sales_summary['count'] or 0
    avg_ticket = (sales_total / sales_count) if sales_count > 0 else Decimal('0.00')

    # Ventas agrupadas por día para gráfica
    daily_sales_qs = (
        sales_qs.values('date__date')
        .annotate(total=Sum('total'))
        .order_by('date__date')
    )
    sales_chart_labels = [row['date__date'].strftime('%d/%m') for row in daily_sales_qs]
    sales_chart_data = [float(row['total'] or 0) for row in daily_sales_qs]

    # 2. Productos más vendidos y menor rotación
    top_products = list(
        SaleItem.objects.filter(
            sale__status=Sale.STATUS_COMPLETED,
            sale__date__date__gte=date_from,
            sale__date__date__lte=date_to,
        )
        .values('product__id', 'product__sku', 'product__name', 'product__category__name')
        .annotate(units=Sum('quantity'), revenue=Sum('subtotal'))
        .order_by('-units')[:10]
    )

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
    active_products = Product.objects.select_related('category').filter(is_active=True)
    low_rotation_products = sorted(
        [{'product': p, 'units': sold_map.get(p.id, 0)} for p in active_products],
        key=lambda x: (x['units'], -x['product'].stock),
    )[:10]

    # 3. Finanzas (Ingresos, Egresos y Ganancia Estimada)
    fin_qs = FinancialMovement.objects.select_related('category').filter(
        is_cancelled=False,
        date__date__gte=date_from,
        date__date__lte=date_to,
    )
    income_total = fin_qs.filter(
        movement_type=FinancialMovement.TYPE_INCOME
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expense_total = fin_qs.filter(
        movement_type=FinancialMovement.TYPE_EXPENSE
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    estimated_profit = income_total - expense_total

    finance_by_category = list(
        fin_qs.values('category__name', 'movement_type')
        .annotate(total=Sum('amount'))
        .order_by('movement_type', '-total')
    )

    # 4. Cuentas por Cobrar y Pagar activas
    receivables = CustomerDebt.objects.select_related('customer', 'sale').filter(
        is_paid=False, is_cancelled=False
    )
    total_receivables = receivables.aggregate(total=Sum('pending_balance'))['total'] or Decimal('0.00')

    payables = SupplierDebt.objects.select_related('supplier', 'purchase').filter(
        is_paid=False, is_cancelled=False
    )
    total_payables = payables.aggregate(total=Sum('pending_balance'))['total'] or Decimal('0.00')

    # 5. Movimientos de Inventario recientes del período
    inventory_movements = InventoryMovement.objects.select_related('product', 'user').filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )[:20]

    context = {
        'title': 'Reportes y Estadísticas',
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'preset': preset,
        'sales_total': sales_total,
        'sales_count': sales_count,
        'avg_ticket': avg_ticket,
        'sales_list': sales_qs[:20],
        'sales_chart_labels_json': json.dumps(sales_chart_labels),
        'sales_chart_data_json': json.dumps(sales_chart_data),
        'top_products': top_products,
        'low_rotation_products': low_rotation_products,
        'income_total': income_total,
        'expense_total': expense_total,
        'estimated_profit': estimated_profit,
        'finance_by_category': finance_by_category,
        'receivables': receivables[:20],
        'total_receivables': total_receivables,
        'payables': payables[:20],
        'total_payables': total_payables,
        'inventory_movements': inventory_movements,
    }
    return render(request, 'reports/dashboard.html', context)


@login_required
@admin_required
def export_report_excel(request):
    """Exporta a Excel (.xlsx) el reporte solicitado en el rango de fechas."""
    report_type = request.GET.get('report', 'sales')
    date_from, date_to, _ = _parse_date_range(request)
    try:
        title, headers, rows = build_report_dataset(report_type, date_from, date_to)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('reports:dashboard')

    filename = f"storeflow_{report_type}_{date_from}_{date_to}"
    return export_to_excel(title, headers, rows, filename)


@login_required
@admin_required
def export_report_pdf(request):
    """Exporta a PDF el reporte solicitado en el rango de fechas."""
    report_type = request.GET.get('report', 'sales')
    date_from, date_to, _ = _parse_date_range(request)
    try:
        title, headers, rows = build_report_dataset(report_type, date_from, date_to)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('reports:dashboard')

    subtitle = f"Período: {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}"
    filename = f"storeflow_{report_type}_{date_from}_{date_to}"
    return export_to_pdf(title, subtitle, headers, rows, filename)
