from django import forms
from .models import Supplier

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
