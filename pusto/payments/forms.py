from django import forms
from django.utils.translation import gettext_lazy as _
from .models import PendingAdvPromotion


class AdvertisementForm(forms.ModelForm):
    class Meta:
        model = PendingAdvPromotion
        fields = ['title', 'image', 'link']

        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': _('заголовок который будет отображаться при наведении'),
                'class': 'form-input',
            }),
            'link': forms.URLInput(attrs={
                'placeholder': _('https://example.com'),
                'class': 'form-input',
            }),
        }

    # (опционально) переводы label
    title = forms.CharField(label=_('Заголовок'))
    image = forms.ImageField(label=_('Изображение'))
    link = forms.URLField(label=_('Ссылка'))