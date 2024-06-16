import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Feedback
from .utils import analyse_sentiment

logger = logging.getLogger("app")


@receiver(post_save, sender=Feedback)
def analyse_feedback_sentiment(sender, instance, created, **kwargs):
    logger.info("Signal Trigger: feedback sentiment analysis")
    if created and instance.message:
        sentiment = analyse_sentiment(instance.message)
        Feedback.objects.filter(pk=instance.pk).update(
            sentiment=sentiment
        )  # instance.save calls the signal twice
        logger.info("Signal Trigger: Sentiment analysed")
