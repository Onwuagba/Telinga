# serializers.py
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import APIKey, MessageFormat, Customer, Feedback


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    confirm_password = serializers.CharField(
        write_only=True, required=True)

    class Meta:
        model = User
        fields = ("username", "password", "confirm_password", "email")

    def validate(self, data):
        if not data.get("password") or not data.get("confirm_password"):
            raise serializers.ValidationError(
                "Please enter a password and confirm it")
        if data.get("password") != data.get("confirm_password"):
            raise serializers.ValidationError(
                "Your passwords do not match")

        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_staff=True,
        )
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = get_user_model().objects.create_user(**validated_data)
        return user


class UpdatePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "Current password is incorrect.")
        return value

    def update(self, instance, validated_data):
        instance.set_password(validated_data["new_password"])
        instance.save()
        return instance


class APIKeySerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(
        source="business.username", read_only=True)

    class Meta:
        model = APIKey
        fields = ["key", "business", "business_name", "created_at"]
        read_only_fields = ["key"]


class MessageFormatSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageFormat
        fields = ["id", "message", "business", "created_at"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["phone_number", "email",
                  "first_name", "last_name", "message_format"]


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "customer", "message",
                  "sentiment", "created_at"]
        read_only_fields = ["sentiment"]
