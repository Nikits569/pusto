from .models import *
from django import forms
from django.utils.translation import gettext_lazy as _

class NotificationNeighborForm(forms.ModelForm):
    type = forms.ChoiceField(
        choices=[
            ('findNeighbor', 'find neighbor'),
            ('rent', 'rent'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = notification
        fields = ['email', 'city', 'type', 'budget_from', 'budget_to', 'rooms']

        widgets = {
            'created_at': forms.DateTimeInput(attrs={'type': 'datetime'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            #'type': forms.Select(attrs={'class': 'form-select'}),

        }


class NotificationThingsForm(forms.ModelForm):
    type = forms.ChoiceField(
        choices=[
            ('sell_category', 'sell'),
            ('buy_category', 'buy')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = notification
        fields = ['email', 'city', 'type', 'category', 'budget_from', 'budget_to']
        widgets = {
            'created_at': forms.DateTimeInput(attrs={'type': 'datetime'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            # 'type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'ntf-input', 'placeholder': 'you@example.com'}),
        }
        labels = {
            'budget_from': _('Ціна від'),
            'budget_to': _('Ціна до'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = False
        self.fields['type'].required = False
        self.fields['category'].required = False
        self.fields['budget_from'].required = False
        self.fields['budget_to'].required = False
        self.fields['email'].required = True