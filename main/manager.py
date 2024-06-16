import logging
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings


logger = logging.getLogger("app")

class CustomerNotificationManager:
    def __init__(self, account_sid, auth_token, twilio_phone_number, email_from):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.twilio_phone_number = twilio_phone_number
        self.email_from = email_from

    def generate_email_subject(self, message):
        """
        Generates an email subject based on the provided message.

        This is a placeholder function. You can customize the logic to
        extract keywords or phrases from the message and create a dynamic
        subject line.

        Args:
            message: The message content used to generate the subject.

        Returns:
            A string representing the generated email subject.
        """

        # Placeholder implementation (customize as needed)
        keywords = ["promotion", "discount", "update"]
        if any(keyword in message.lower() for keyword in keywords):
            return f"Important: {message[:30]}"  # Truncate to 30 chars
        else:
            return f"From Your Company: {message[:30]}"

    def send_message(self, customer):
        logging.info(
            f"Notification service called by {customer.first_name} for business `{customer.message_format.business.first_name}`"
        )
        if customer.phone_number:
            logging.info(
                f"{customer.first_name} has a phone number {customer.phone_number}"
            )
            self.send_sms(
                customer.phone_number,
                self.parse_message(customer.message_format.message, customer),
            )
            logging.info(f"Notification to {customer.first_name} completed")
        elif customer.email:
            logging.info(f"{customer.first_name} has email address {customer.email}")
            subject = self.generate_email_subject(customer.message_format.message)
            self.send_email(
                customer.email,
                subject,
                self.parse_message(customer.message_format.message, customer),
            )
            logging.info(f"Notification to {customer.first_name} completed")
        else:
            logging.error("Customer does not have a phone number or email")

    def send_sms(self, phone_number, message):
        logging.info(f"Sending SMS to phone number {phone_number}")
        client = Client(self.account_sid, self.auth_token)
        message = client.messages.create(
            body=message, from_=self.twilio_phone_number, to=phone_number
        )
        logger.info(f"SMS sent to {phone_number}: {message.sid}")

    def send_email(self, email, subject, message):
        logging.info(f"Sending email to {email}")
        send_mail(
            subject=subject,
            message=message,
            from_email=self.email_from,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"Email sent to {email}")

    def parse_message(self, message_format, customer):
        logging.info(f"Parsing message for {customer.first_name}")
        parsed_message = message_format
        for header in settings.CSV_REQUIRED_HEADERS:
            placeholder = f"{{{{ {header} }}}}"
            if placeholder in parsed_message:
                value = getattr(customer, header)
                parsed_message = parsed_message.replace(placeholder, value)
            else:
                logging.error(
                    f"Placeholder {placeholder} not found in the message format"
                )
                # raise ValueError(
                #     f"Placeholder {placeholder} not found in the message format"
                # )
        return parsed_message

