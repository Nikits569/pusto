from django import forms
from django.utils.translation import gettext_lazy as _
from accounts.models import *
from .models import *
from ads.models import *


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'city', 'avatar']
        widgets = {
            'city': forms.Select(attrs={
                'class': 'form-select'
            })
        }


class EmployerVerificationForm(forms.ModelForm):
    class Meta:
        model = Employer
        fields = ['ico', 'company_name']
        widgets = {
            'ico': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': _('IČO компанії')
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': _('Назва компанії')
            }),
        }


class BaseEditForm(forms.ModelForm):
    city = forms.ChoiceField(
        choices=[('', _('оберіть місто'))] + list(City.choices),
        widget=forms.Select(attrs={'class': 'custom-select ui-field type2'}),
        required=True,
        label='',
    )

    class Meta:
        fields = ['title', 'text', 'city']
        labels = {
            'title': '',
            'text': '',
            'city': '',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': _('заголовок')
            }),
            'text': forms.Textarea(attrs={
                'placeholder': _('опис')
            }),
            'city': forms.Select(attrs={
                'class': 'custom-select ui-field type2'
            }),
        }


class JobPostEditForm(BaseEditForm):
    class Meta(BaseEditForm.Meta):
        model = JobPost


class ThingsPostEditForm(BaseEditForm):
    class Meta(BaseEditForm.Meta):
        model = ThingsPost


class NeighborPostEditForm(BaseEditForm):
    class Meta(BaseEditForm.Meta):
        model = NeighborPost