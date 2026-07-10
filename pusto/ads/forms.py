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
            'telegram_username': forms.TextInput(attrs={'placeholder': _('telegram')}),
            'email': forms.TextInput(attrs={'placeholder': _('email*')}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and user.is_authenticated and user.email:
            self.fields['email'].initial = user.email
            self.fields['email'].widget.attrs['readonly'] = 'readonly'


class ThingsPostForm(BasePostForm):
    category = forms.ModelChoiceField(
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
            'telegram_username',
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
            'telegram_username',
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
        self.fields['telegram_username'].label = _('Telegram')

        self.fields['employment_type'].required = False
        self.fields['salary_from'].required = False
        self.fields['salary_to'].required = False
        self.fields['salary_period'].required = False
        self.fields['company_name'].required = False


class NeighborPostForm(BasePostForm):
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
            'my_lifestyles': forms.CheckboxSelectMultiple(),
            'neighbor_lifestyles': forms.CheckboxSelectMultiple(),
            'housing_type': forms.Select(),
            #'move_in_date': forms.DateInput(attrs={'type': 'date'}),
        }
        fields = [
            'title',
            'text',
            'city',
            'count_neighbors',
            'my_gender',
            'neighbor_gender',
            'my_age',
            'min_age',
            'max_age',
            'budget',
            'rent_period',
            'my_lifestyles',
            'neighbor_lifestyles',
            'housing_type',
            #'move_in_date',
            'email',
            'telegram_username',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['title'].label = _('Заголовок')
        self.fields['text'].label = _('Опис')
        self.fields['city'].label = _('Місто')
        self.fields['count_neighbors'].label = _('Кількість сусідів')
        self.fields['my_gender'].label = _('Моя стать')
        self.fields['neighbor_gender'].label = _('Стать сусіда')
        self.fields['my_age'].label = _('Мій вік')
        self.fields['min_age'].label = _('Мінімальний вік')
        self.fields['max_age'].label = _('Максимальний вік')
        self.fields['budget'].label = _('Бюджет')
        self.fields['rent_period'].label = _('Період оренди')
        self.fields['my_lifestyles'].label = _('Мій стиль життя')
        self.fields['neighbor_lifestyles'].label = _('Стиль життя сусіда')
        self.fields['housing_type'].label = _('Тип житла')
        #self.fields['move_in_date'].label = _('Дата заселення')
        self.fields['email'].label = _('Email')
        self.fields['telegram_username'].label = _('Telegram')

        self.fields['count_neighbors'].required = False
        self.fields['my_gender'].required = False
        self.fields['neighbor_gender'].required = False
        self.fields['min_age'].required = False
        self.fields['max_age'].required = False
        self.fields['budget'].required = True
        self.fields['rent_period'].required = False
        self.fields['my_lifestyles'].required = False
        self.fields['neighbor_lifestyles'].required = False
        self.fields['housing_type'].required = False
        #self.fields['move_in_date'].required = False

        self.fields['title'].widget.attrs.update({'placeholder': _('заголовок*')})
        self.fields['text'].widget.attrs.update({'placeholder': _('опис')})
        self.fields['city'].widget.attrs.update({'placeholder': _('будь-яке місто')})
        self.fields['count_neighbors'].widget.attrs.update({'placeholder': _('кількість сусідів')})
        self.fields['min_age'].widget.attrs.update({'placeholder': _('мінімальний вік')})
        self.fields['max_age'].widget.attrs.update({'placeholder': _('максимальний вік')})
        self.fields['budget'].widget.attrs.update({'placeholder': _('бюджет (з людини € )')})
        self.fields['email'].widget.attrs.update({'placeholder': _('email*')})
        self.fields['telegram_username'].widget.attrs.update({'placeholder': _('telegram')})


ThingsPostImageFormSet = post_image_formset(ThingsPost, ThingsPostImage)
JobPostImageFormSet = post_image_formset(JobPost, JobPostImage)
NeighborPostImageFormSet = post_image_formset(NeighborPost, NeighborPostImage)