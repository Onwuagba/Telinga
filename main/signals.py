import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Feedback
from .utils import gemini_manager, message_manager

logger = logging.getLogger("app")


@receiver(post_save, sender=Feedback)
def analyse_feedback_sentiment(sender, instance, created, **kwargs):
    logger.info("Signal Trigger: feedback sentiment analysis")
    if created and instance.message:
        sentiment = gemini_manager._sentiment_analysis(instance.message)

        # Temporarily disconnect the signal so save does not call it twice
        post_save.disconnect(analyse_feedback_sentiment, sender=Feedback)

        instance.sentiment = sentiment
        instance.save()

        # Reconnect the signal
        post_save.connect(analyse_feedback_sentiment, sender=Feedback)

        logger.info("Signal Trigger: Sentiment analysed")

        # Handle feedback response based on sentiment
        message_manager.respond_to_feedback(instance)

        if sentiment == "negative":
            message_manager.escalate_to_agent(instance)
