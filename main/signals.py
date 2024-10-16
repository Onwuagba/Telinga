import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from main.models import APIKey, MessageFormat, Customer,  Feedback, MessageStatus
from main.utils import gemini_manager, message_manager

logger = logging.getLogger("app")


@receiver(post_save, sender=Feedback)
def analyse_feedback_sentiment(sender, instance, created, **kwargs):
    logger.info(
        "Signal Trigger: starting feedback sentiment analysis. ..")
    if created and instance.message:
        sentiment = gemini_manager._sentiment_analysis(
            instance.message)
        Feedback.objects.filter(pk=instance.pk).update(
            sentiment=sentiment
        )  # instance.save calls the signal twice

        logger.info("Signal Trigger: Sentiment analysed")

        # Handle feedback response based on sentiment
        message_manager.respond_to_feedback(instance)

        if sentiment == "negative":
            message_manager.escalate_to_agent(instance)


@receiver(post_save, sender=User)
def assign_permissions(sender, instance, created, **kwargs):
    if created:
        # Retrieve content types for each model
        api_key_content_type = ContentType.objects.get_for_model(
            APIKey)
        message_format_content_type = ContentType.objects.get_for_model(
            MessageFormat)
        customer_content_type = ContentType.objects.get_for_model(
            Customer)
        feedback_content_type = ContentType.objects.get_for_model(
            Feedback)
        msg_status_content_type = ContentType.objects.get_for_model(
            MessageStatus)

        # CRUD permissions for APIKey model
        api_key_permissions = ["view_apikey", "change_apikey"]
        for codename in api_key_permissions:
            permission = Permission.objects.get(
                codename=codename, content_type=api_key_content_type
            )
            instance.user_permissions.add(permission)

        # CRUD permissions for MessageFormat model
        message_format_permissions = [
            "view_messageformat",
            "change_messageformat",
        ]
        for codename in message_format_permissions:
            permission = Permission.objects.get(
                codename=codename, content_type=message_format_content_type
            )
            instance.user_permissions.add(permission)

        # CRUD permissions for Customer model
        customer_permissions = ["view_customer",
                                "change_customer", "delete_customer"]
        for codename in customer_permissions:
            permission = Permission.objects.get(
                codename=codename, content_type=customer_content_type
            )
            instance.user_permissions.add(permission)

        # view permission for Feedback model
        feedback_permissions = ["view_feedback"]
        for codename in feedback_permissions:
            permission = Permission.objects.get(
                codename=codename, content_type=feedback_content_type
            )
            instance.user_permissions.add(permission)

        # view permission for MessageStatus model
        messagestatus_permissions = [
            "view_messagestatus", "delete_messagestatus"]
        for codename in messagestatus_permissions:
            permission = Permission.objects.get(
                codename=codename, content_type=msg_status_content_type
            )
            instance.user_permissions.add(permission)
