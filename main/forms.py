from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django import forms
from django.core.exceptions import ValidationError
from main.models import Customer, MessageFormat


class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(CustomerAdminForm, self).__init__(*args, **kwargs)
        user = self.current_user
        if not user.is_superuser:
            self.fields["message_format"].queryset = MessageFormat.objects.filter(
                business=user
            )

    def clean(self):
        cleaned_data = super().clean()
        message_format = cleaned_data.get('message_format')

        # Perform validation to ensure message_format is selected
        if not message_format:
            raise ValidationError('Message format must be selected.')


class AdminRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'style': 'width: 96%;'})
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={'style': 'width: 96%;'})
    )

    class Meta:
        model = get_user_model()
        fields = ('username', 'email')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match."))
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_staff = True
        if commit:
            user.save()
        return user
