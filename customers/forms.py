from django import forms
from .models import Customer

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
