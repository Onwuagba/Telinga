# models.py
import secrets
from django.db import models
from django.contrib.auth import get_user_model


UserModel = get_user_model()


class APIKey(models.Model):
    key = models.CharField(max_length=40, unique=True, default=secrets.token_urlsafe)
    user = models.ForeignKey(
        UserModel, on_delete=models.CASCADE, related_name="user_key"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key
