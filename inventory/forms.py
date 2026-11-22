from django import forms
from .models import Product, Category, InventoryMovement

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'description', 'cost_price', 'sale_price', 'stock', 'min_stock', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Arroz Diana 1kg'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. PROD-001'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción detallada (opcional)'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip().upper()
        qs = Product.objects.filter(sku__iexact=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un producto registrado con este código o SKU.")
        return sku

    def clean(self):
        cleaned_data = super().clean()
        cost_price = cleaned_data.get('cost_price')
        sale_price = cleaned_data.get('sale_price')

        if cost_price is not None and sale_price is not None:
            if sale_price < cost_price:
                self.add_error('sale_price', 'El precio de venta no debería ser inferior al precio de compra.')
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Abarrotes, Bebidas'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la categoría'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una categoría con este nombre.")
        return name


class ManualStockMovementForm(forms.Form):
    MOVEMENT_CHOICES = [
        (InventoryMovement.MOVEMENT_IN, 'Entrada de Mercancía (Añadir al stock)'),
        (InventoryMovement.MOVEMENT_OUT, 'Salida Manual (Mermas, daño o retiro)'),
        (InventoryMovement.MOVEMENT_ADJUSTMENT, 'Ajuste de Conteo Físico (Sobrescribir stock real)'),
    ]

    movement_type = forms.ChoiceField(
        choices=MOVEMENT_CHOICES,
        label='Tipo de Movimiento',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        min_value=0,
        label='Cantidad / Conteo',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese la cantidad'})
    )
    reference = forms.CharField(
        max_length=150,
        label='Motivo / Referencia',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Conteo físico fin de mes, Devolución cliente'})
    )
    notes = forms.CharField(
        required=False,
        label='Observaciones adicionales',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Detalles adicionales...'})
    )
