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

