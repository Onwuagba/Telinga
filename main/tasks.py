import logging
import time
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from main.models import Customer, MessageStatus
from main.utils import message_manager, nylas_client

logger = logging.getLogger("app")


@shared_task(bind=True, max_retries=3)
def schedule_message(self, customer_id):
    logger.info("Enter celery to send message to customer")
    customer = Customer.objects.get(id=customer_id)
    try:
        message_manager.send_message(customer)
    except TwilioRestException as e:
        logger.error(f"Task failed due to TwilioRestException: {e}")
        self.update_state(
            state="FAILURE", meta={"exc_type": type(e).__name__, "exc_message": str(e)}
        )
        raise Ignore()  # Mark task as failed without retrying
    except Exception as e:
        logger.error(
            f"MessageTask failed due to an unexpected error: {e}")
        # Retry the task after 60 seconds
        self.retry(exc=e, countdown=60)


@shared_task
def check_message_delivery_status():
    client = Client(settings.ACCOUNT_SID, settings.AUTH_TOKEN)
    message_statuses = MessageStatus.objects.filter(
        status__in=["queued", "sending", "sent"]
    )

    for message_status in message_statuses:
        try:
            message = client.messages(
                message_status.message_sid).fetch()
            message_status.status = message.status
            message_status.save()
        except Exception as e:
            # Log the exception
            logger.error(
                f"Error fetching message status for {message_status.message_sid}: {e}"
            )
