from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    Category,
    ThingsPost,
    ThingsPostImage,
    JobPost,
    JobPostImage,
    NeighborPost,
    NeighborPostImage,
    City,
    Condition,
    Lifestyle,
)
from django.utils.translation import get_language

class TranslatedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        lang = get_language() or 'uk'
        lang = lang.split('-')[0]
        return (
            getattr(obj, f'name_{lang}', None)
            or getattr(obj, 'name_uk', None)
            or str(obj)
        )


class TranslatedModelChoiceField(forms.ModelChoiceField):
    """
    Аналог TranslatedModelMultipleChoiceField, но для одиночного выбора
    (используется для Category, у которой поля title_uk / title_en / title_sk).
    """
    def label_from_instance(self, obj):
        lang = get_language() or 'uk'
        lang = lang.split('-')[0]
        return (
            getattr(obj, f'title_{lang}', None)
            or getattr(obj, 'title_uk', None)
            or str(obj)
        )

class BasePostForm(forms.ModelForm):
    city = forms.ChoiceField(
        choices=[('', _('оберіть місто'))] + list(City.choices),
        widget=forms.Select(attrs={'class': 'custom-select ui-field type2'}),
        required=True,
    )

    class Meta:
        model = None
        fields = []
        widgets = {
            'case_type': forms.Select(),
            'title': forms.TextInput(attrs={'placeholder': _('заголовок*')}),
            'text': forms.Textarea(attrs={'placeholder': _('опис')}),
            #'telegram_username': forms.TextInput(attrs={'placeholder': _('telegram')}),
            'email': forms.TextInput(attrs={'placeholder': _('email*')}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and user.is_authenticated and user.email:
            self.fields['email'].initial = user.email
            self.fields['email'].widget.attrs['readonly'] = 'readonly'


class ThingsPostForm(BasePostForm):
    category = TranslatedModelChoiceField(
        queryset=Category.objects.filter(is_active=True).order_by("order"),
        widget=forms.RadioSelect,
        empty_label=None,
        label=_("категорія")
    )

    condition = forms.ChoiceField(
        choices=[('', _('оберіть стан'))] + list(Condition.choices),
        widget=forms.Select(attrs={'class': 'custom-select ui-field type2'}),
        required=False,
    )

    class Meta(BasePostForm.Meta):
        model = ThingsPost
        widgets = BasePostForm.Meta.widgets | {
            'price': forms.TextInput(attrs={'placeholder': _('ціна(€)*')})
        }
        fields = [
            'title',
            'price',
            'text',
            'city',
            'condition',
            'category',
            'email',
            #'telegram_username',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)




def post_image_formset(parent_model, image_model):
    return inlineformset_factory(
        parent_model,
        image_model,
        fields=('image',),
        extra=1,
        can_delete=True
    )


class JobPostForm(BasePostForm):
    class Meta(BasePostForm.Meta):
        model = JobPost
        widgets = BasePostForm.Meta.widgets | {
            'salary_from': forms.TextInput(attrs={'placeholder': _('зарплата від')}),
            'salary_to': forms.TextInput(attrs={'placeholder': _('зарплата до')}),
            'company_name': forms.TextInput(attrs={'placeholder': _('назва компанії')}),
        }
        fields = [
            'title',
            'text',
            'city',
            'employment_type',
            'salary_from',
            'salary_to',
            'salary_period',
            'company_name',
            'email',
            #'telegram_username',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['title'].label = _('Назва вакансії')
        self.fields['text'].label = _('Опис')
        self.fields['city'].label = _('Місто')
        self.fields['employment_type'].label = _('Тип зайнятості')
        self.fields['salary_from'].label = _('Зарплата від')
        self.fields['salary_to'].label = _('Зарплата до')
        self.fields['salary_period'].label = _('Період зарплати')
        self.fields['company_name'].label = _('Назва компанії')
        self.fields['email'].label = _('Email')
        #self.fields['telegram_username'].label = _('Telegram')

        self.fields['employment_type'].required = False
        self.fields['salary_from'].required = False
        self.fields['salary_to'].required = False
        self.fields['salary_period'].required = False
        self.fields['company_name'].required = False


class NeighborPostForm(BasePostForm):
    #my_lifestyles = TranslatedModelMultipleChoiceField(
    #    queryset=Lifestyle.objects.all(),
    #    widget=forms.CheckboxSelectMultiple,
    #    required=False,
    #    label=_('Мій стиль життя'),
    #)
    #neighbor_lifestyles = TranslatedModelMultipleChoiceField(
    #    queryset=Lifestyle.objects.all(),
    #    widget=forms.CheckboxSelectMultiple,
    #    required=False,
    #    label=_('Стиль життя сусіда'),
    #)

    class Meta(BasePostForm.Meta):
        model = NeighborPost
        widgets = BasePostForm.Meta.widgets | {
            'count_neighbors': forms.NumberInput(attrs={'placeholder': _('кількість сусідів')}),
            'my_gender': forms.Select(),
            'neighbor_gender': forms.Select(),
            'min_age': forms.NumberInput(attrs={'placeholder': _('мінімальний вік')}),
            'max_age': forms.NumberInput(attrs={'placeholder': _('максимальний вік')}),
            'budget': forms.NumberInput(attrs={'placeholder': _('бюджет')}),
            'rent_period': forms.Select(),
            'housing_type': forms.Select(),
        }
        fields = [
            'title', 'text', 'city', 'count_neighbors',
            'my_gender', 'neighbor_gender', 'my_age', 'min_age', 'max_age',
            'budget', 'rent_period',
            #'my_lifestyles', 'neighbor_lifestyles',
            'housing_type', 'email',
        ]


class RentPostForm(BasePostForm):
    class Meta(BasePostForm.Meta):
        model = NeighborPost

        widgets = BasePostForm.Meta.widgets | {
            'city': forms.Select(),

            'housing_type': forms.Select(),

            'budget': forms.NumberInput(attrs={
                'placeholder': _('ціна за місяць (€)')
            }),

            'count_neighbors': forms.NumberInput(attrs={
                'placeholder': _('кількість мешканців')
            }),

            'move_in_date': forms.DateInput(attrs={
                'type': 'date'
            }),
        }

        fields = [
            'title',
            'text',

            'city',
            'housing_type',
            'budget',
            'count_neighbors',
            'move_in_date',

            'email',
            'telegram_username',
        ]

ThingsPostImageFormSet = post_image_formset(ThingsPost, ThingsPostImage)
JobPostImageFormSet = post_image_formset(JobPost, JobPostImage)
NeighborPostImageFormSet = post_image_formset(NeighborPost, NeighborPostImage)