"""Account forms.

Registration goes through :class:`~django.contrib.auth.forms.UserCreationForm`
so Django's password validators (length, common-password and numeric-only
checks configured in settings) actually run.  The original hand-rolled form
accepted any password, including "1".
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    display_name = forms.CharField(label='姓名', max_length=64)
    organization = forms.ChoiceField(
        label='單位',
        choices=[
            ('教學醫院', '教學醫院'),
            ('區域醫院', '區域醫院'),
            ('研究中心', '研究中心'),
        ],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '帳號'
        self.fields['password1'].label = '密碼'
        self.fields['password2'].label = '確認密碼'
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
