from django import forms
from django.utils import timezone
from .models import FinancialCategory, FinancialMovement


class FinancialCategoryForm(forms.ModelForm):
    class Meta:
        model = FinancialCategory
        fields = ['name', 'movement_type', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pago de Servicios, Arriendo...'}),
            'movement_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción opcional...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('El nombre de la categoría es obligatorio.')
        return name


class FinancialMovementForm(forms.ModelForm):
    date = forms.DateTimeField(
        label='Fecha y Hora',
        initial=timezone.now,
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
    )

    class Meta:
        model = FinancialMovement
        fields = ['movement_type', 'category', 'description', 'amount', 'date', 'payment_method', 'notes']
        widgets = {
            'movement_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_movement_type'}),
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'id_category'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pago recibo energía mes actual'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones adicionales...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = FinancialCategory.objects.filter(is_active=True)
        if not self.is_bound:
            self.initial['date'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        movement_type = cleaned_data.get('movement_type')
        category = cleaned_data.get('category')
        if movement_type and category and category.movement_type != movement_type:
            raise forms.ValidationError(
                f'La categoría "{category.name}" es de tipo {category.get_movement_type_display()}, '
                f'no coincide con el tipo de movimiento seleccionado.'
            )
        return cleaned_data
