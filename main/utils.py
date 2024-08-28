from django.conf import settings
from main.manager import CustomerNotificationManager, GeminiManager, nylas_client


gemini_manager = GeminiManager()
nylas_client = nylas_client


message_manager = CustomerNotificationManager(
    account_sid=settings.ACCOUNT_SID,
    auth_token=settings.AUTH_TOKEN,
    twilio_phone_number=settings.TWILIO_PHONE_NUMBER,
    email_from=settings.EMAIL_SENDER,
)

# # Fetch the customers and send messages to each
# customers = Customer.objects.all()
# for customer in customers:
#     message_manager.send_message(customer)
