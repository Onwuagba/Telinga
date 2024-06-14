# models.py
import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, MaxLengthValidator

from main.utils import analyse_sentiment


UserModel = get_user_model()


class APIKey(models.Model):
    key = models.CharField(max_length=40, unique=True, default=secrets.token_urlsafe)
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="user_key"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key


class Customer(models.Model):
    # table holding customers data
    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(regex=r"^\d+$", message="Phone number must be numeric")
        ],
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )
    email = models.EmailField(null=True, blank=True, unique=True, db_index=True)
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        if self.first_name:
            return f"{self.first_name} {self.last_name}"
        else:
            return self.phone_number or self.email


class Feedback(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="feedback"
    )
    message = models.TextField(validators=[MaxLengthValidator(limit_value=1000)])
    sentiment = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "feedback"

    def __str__(self):
        return f"{self.customer.first_name} feedback"

    def save(self, *args, **kwargs):
        if self._state.adding and self.message:
            self.sentiment = analyse_sentiment(self.message)
        super(Feedback, self).save(*args, **kwargs)
