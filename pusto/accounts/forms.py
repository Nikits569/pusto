from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_('Пароль'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('пароль'),
        })
    )
    password2 = forms.CharField(
        label=_('Повторіть пароль'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('повторіть пароль'),
        })
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': _('email'),
            }),
            'first_name': forms.TextInput(attrs={
                'placeholder': _("Ім'я"),
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': _('прізвище'),
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                _('користувач із таким email вже існує')
            )
        return email

    def clean(self):
        cd = super().clean()
        if cd.get('password1') != cd.get('password2'):
            raise forms.ValidationError(
                _('паролі не збігаються')
            )
        return cd

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'placeholder': _('email'),
        })
    )
    password = forms.CharField(
        label=_('Пароль'),
        widget=forms.PasswordInput(attrs={
            'placeholder': _('пароль'),
        })
    )