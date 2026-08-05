from django import forms
from django.utils.translation import gettext_lazy as _
from .models import SupportTicket, ClaimRequest, Reason


class SupportTicketForm(forms.ModelForm):

    class Meta:
        model = SupportTicket
        fields = ('email', 'subject', 'message')
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': _('ваш email'),
                'class': 'firstType',
                'autocomplete': 'off'
            }),
            'subject': forms.TextInput(attrs={
                'placeholder': _('тема (наприклад: Скарга на оголошення)'),
                'class': 'firstType',
                'autocomplete': 'off'
            }),
            'message': forms.Textarea(attrs={
                'placeholder': _('опишіть проблему або поставте запитання'),
                'class': 'secondType',
                'rows': 4
            }),
        }


class ClaimRequestForm(forms.ModelForm):
    reason = forms.ChoiceField(
        label=_('Причина'),
        choices=Reason.choices,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    text = forms.CharField(
        label=_('Описание'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Опишите проблему')
        })
    )

    class Meta:
        model = ClaimRequest
        fields = ['reason', 'text']