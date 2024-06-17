import logging
from celery import shared_task
from celery.exceptions import Ignore
from twilio.base.exceptions import TwilioRestException
from main.models import Customer
from main.utils import message_manager

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
            state='FAILURE',
            meta={'exc_type': type(e).__name__, 'exc_message': str(e)}
        )
        raise Ignore()  # Mark task as failed without retrying
    except Exception as e:
        logger.error(f"MessageTask failed due to an unexpected error: {e}")
        self.retry(exc=e, countdown=60)  # Retry the task after 60 seconds
