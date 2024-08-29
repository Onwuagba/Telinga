import os
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from main.manager import nylas_client
from nylas.models.webhooks import WebhookTriggers

from main.models import NylasWebhook

logger = logging.getLogger("app")

load_dotenv()


class Command(BaseCommand):
    help = "Create a Nylas Webhook"

    def handle(self, *args, **kwargs):
        # Get the domain from settings and construct the callback URL
        domain = settings.SITE_DOMAIN  # Ensure this is set in settings file
        callback_url = f"{domain}api/nylas_webhook/"

        try:
            email = os.getenv("SUPPORT_EMAIL")
            webhook = nylas_client.webhooks.create(
                request_body={
                    "trigger_types": [WebhookTriggers.THREAD_REPLIED],
                    "webhook_url": callback_url,
                    "description": "Telinga Email replies webhook",
                    "notification_email_addresses": [email],
                }
            )
            print(webhook)

            NylasWebhook.objects.create(
                webhook_id=webhook[0].id,
                secret_key=webhook[0].webhook_secret,
                trigger_type='thread.replied',
            )

            self.stdout.write(self.style.SUCCESS(
                f'Webhook created with ID: {webhook[0].id}'))
            logger.info(
                f'Webhook created with ID: {webhook[0].id} and secret : {webhook[0].webhook_secret}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'Failed to create webhook: {e}'))
            logger.error(f'Failed to create webhook: {e}')
