from django import forms
from .models import Customer, CustomerPayment

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'document_id', 'phone', 'email', 'address', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan Pérez'}),
            'document_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. C.C. o NIT'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 300 123 4567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección de residencia o negocio'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas crediticias o de contacto'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('El nombre del cliente es obligatorio.')
        return name


class CustomerPaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        label='Valor del Abono',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
    )
    payment_method = forms.ChoiceField(
        choices=CustomerPayment.PAYMENT_METHOD_CHOICES,
        label='Método de Pago',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    notes = forms.CharField(
        required=False,
        label='Observaciones',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones opcionales...'})
    )
