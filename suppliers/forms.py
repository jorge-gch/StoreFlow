from django import forms
from .models import Supplier, SupplierPayment

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'tax_id', 'phone', 'email', 'address', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Distribuidora Central S.A.S.'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. María Gómez (Ejecutiva de cuenta)'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 900.123.456-7'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +57 601 234 5678 / 310 987 6543'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'pedidos@proveedor.com'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección de bodega o despacho'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Condiciones de pago, días de entrega, etc.'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('El nombre de la empresa o proveedor es obligatorio.')
        return name


class SupplierPaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        label='Valor del Pago',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
    )
    payment_method = forms.ChoiceField(
        choices=SupplierPayment.PAYMENT_METHOD_CHOICES,
        label='Método de Pago',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reference = forms.CharField(
        required=False,
        max_length=100,
        label='Referencia / Comprobante',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de transferencia, recibo, etc.'})
    )
    notes = forms.CharField(
        required=False,
        label='Observaciones',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones opcionales...'})
    )
