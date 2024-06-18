# models.py
import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MaxLengthValidator
from django.utils.translation import gettext_lazy as _

UserModel = get_user_model()
# a typical user on the system is a business


class APIKey(models.Model):
    key = models.CharField(max_length=40, unique=True, default=secrets.token_urlsafe)
    business = models.OneToOneField(
        UserModel, on_delete=models.CASCADE, related_name="business_key"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key


class MessageFormat(models.Model):
    message = models.TextField()
    business = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="business_message"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id}:{self.business}"


class Customer(models.Model):
    # table holding customers data
    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(regex=r"^\d+$", message="Phone number must be numeric")
        ],
        null=True,
        blank=True,
        db_index=True,
    )
    email = models.EmailField(null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    message_format = models.ForeignKey(
        MessageFormat, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_uploaded = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["phone_number", "email", "message_format"],
                name="unique_business_customer",
                violation_error_message="Customer already exists for this campaign",
            )
        ]

    def clean(self):
        if not self.email and not self.phone_number:
            raise ValidationError(_("Email and phone number cannot both be null"))

    def __str__(self):
        return (
            f"{self.first_name} {self.last_name}"
            if self.first_name
            else (self.phone_number or self.email)
        )


class Feedback(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="customer_feedback"
    )
    message = models.TextField(validators=[MaxLengthValidator(1000)])
    source = sentiment = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[
            ("sms", "sms"),
            ("email", "email"),
        ],
    )
    sentiment = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[
            ("positive", "positive"),
            ("negative", "negative"),
            ("neutral", "neutral"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "feedback"

    def __str__(self):
        return f"{self.customer.first_name} feedback"


class MessageStatus(models.Model):
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="message_status"
    )
    message_sid = models.CharField(max_length=34, unique=True)  # Twilio message SID
    status = models.CharField(max_length=20)  # Delivery status
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Message status"

    def __str__(self):
        return f"{self.status}"
