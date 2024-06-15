# serializers.py
from rest_framework import serializers
from .models import APIKey, MessageFormat, Customer, Feedback


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ["key", "business", "created_at"]
        read_only_fields = ["key"]


class MessageFormatSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageFormat
        fields = ["id", "message", "business", "created_at"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["phone_number", "email", "first_name", "last_name", "message_format"]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "customer", "message", "sentiment", "created_at"]
        read_only_fields = ["sentiment"]
