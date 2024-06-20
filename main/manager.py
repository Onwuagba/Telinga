import logging, os
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import google.generativeai as genai
from twilio.rest import Client

from main.models import Feedback, MessageStatus

load_dotenv()

genai.configure(api_key=os.getenv("TW_GEMINI_API_KEY"))
logger = logging.getLogger("app")


class GeminiManager:
    def __init__(self) -> None:
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _generate_response(self, prompt, message=None):
        try:
            response = self.model.generate_content(prompt)
            if response.parts:
                return response.parts[0].text.strip()
            else:
                logger.error(f"No valid parts in the response. {response}")
                return message or "This is a generic response"
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return message or "This is a generic response"

    def _email_subject(self, message):
        """
        Generates an email subject based on the provided message.

        Args:
            message: The message content for which the email subject is generated.

        Returns:
            The generated email subject as a string.
        """
        logger.info("Generating email subject...")
        prompt = f"Suggest email subject with no extra text for: {message}. Do not add any extra text, simply return only the email title"
        return self._generate_response(prompt, message[:20])

    def _sentiment_analysis(self, feedback):
        """
        Generate sentiment analysis for the given feedback.

        Args:
            feedback (str): The feedback sentence for which sentiment analysis needs to be generated.

        Returns:
            str: The sentiment analysis result, which can be either "positive", "negative", or "neutral".
        """
        logger.info("Generating sentiment analysis...")
        prompt = f"Is this sentence positive or negative or neutral: '{feedback}'? Do not add any extra text, simply return the result"
        result = self._generate_response(prompt).lower()

        if "positive" in result:
            return "positive"
        elif "negative" in result:
            return "negative"
        elif "neutral" in result:
            return "neutral"
        else:
            logger.error(f"Unexpected sentiment analysis result: {result}")
            return "neutral"

    def _summarise_feedback(self, feedback):
        logger.info("Summarising feedback...")
        prompt = f"Summarise this text: {feedback} in two sentences. Make it short and concise"
        return self._generate_response(prompt, feedback[:20])

    def detect_language(self, text):
        logger.info("Detecting language...")
        prompt = f"Detect the language of this text: '{text}'. Return only the language"
        detected_language = self._generate_response(prompt)
        return detected_language.strip().lower()

    def translate_text(self, text, target_language="en"):
        detected_language = self.detect_language(text)
        logger.info(
            f"Translating text from {detected_language} to {target_language}..."
        )
        prompt = f"Translate this text to {target_language}: '{text}'"
        translated_text = self._generate_response(prompt, text[:20])
        return translated_text


class CustomerNotificationManager:
    def __init__(self, account_sid, auth_token, twilio_phone_number, email_from):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.twilio_phone_number = twilio_phone_number
        self.email_from = email_from
        self.gemini_manager = GeminiManager()  # Instantiate GeminiManager

    def generate_email_subject(self, message):
        """
        Generates an email subject based on the provided message.

        Args:
            message: The message content used to generate the subject.

        Returns:
            A string representing the generated email subject.
        """
        # Use GeminiManager to generate the email subject
        return self.gemini_manager._email_subject(message)

    def send_message(self, customer):
        logging.info(
            f"Notification service called by {customer.first_name} for business `{customer.message_format.business.username}`"
        )
        if customer.phone_number:
            logging.info(
                f"{customer.first_name} has a phone number {customer.phone_number}"
            )
            message_sid = self.send_sms(
                f"+{customer.phone_number}",
                self.parse_message(customer.message_format.message, customer),
            )
            logging.info(f"Notification to {customer.first_name} completed")

            # Save message status
            MessageStatus.objects.create(
                customer=customer, message_sid=message_sid, status="queued"
            )
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
        # exception is raised in celery allowing it to fail & retry when necessary
        client = Client(self.account_sid, self.auth_token)
        message = client.messages.create(
            body=message, from_=self.twilio_phone_number, to=phone_number
        )
        logger.info(f"SMS sent to {phone_number}: {message.sid}")

        return message.sid

    def send_email(self, email, subject, message):
        logging.info(f"Sending email to {email}")
        message = Mail(
            from_email=self.email_from,
            to_emails=email,
            subject=subject,
            plain_text_content=message,
        )

        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)

        logger.info(f"Email sent to {email}")

    def parse_message(self, message_format, customer):
        logging.info(f"Parsing message for {customer.first_name}")
        parsed_message = message_format
        for header in settings.CSV_REQUIRED_HEADERS:
            placeholder = f"{{{{{header}}}}}".strip()

            if placeholder in parsed_message:
                value = getattr(customer, header, "")
                parsed_message = parsed_message.replace(placeholder, value)

        return parsed_message

    def respond_to_feedback(self, feedback: Feedback):
        customer = feedback.customer
        logging.info(f"Responding to user feedback from {customer.first_name}")
        message = self.generate_response_message(feedback)
        try:
            if feedback.source == "sms":
                logging.info(
                    f"Feedback from {feedback.customer.first_name} sent via SMS"
                )
                self.send_sms(customer.phone_number, message)
            elif feedback.source == "email":
                logging.info(
                    f"Feedback from {feedback.customer.first_name} sent via email"
                )
                subject = self.generate_email_subject(message)
                self.send_email(customer.email, subject, message)
        except Exception as e:
            logging.error(f"Error sending response to customer: {e}")

    def generate_response_message(self, feedback: Feedback):
        feedback_language = self.gemini_manager.detect_language(feedback.message)

        if feedback.sentiment == "positive":
            response = (
                "Thank you for your positive feedback! We appreciate your support."
            )
        elif feedback.sentiment == "neutral":
            response = "Thank you for your feedback. They are noted and will be taken into consideration"
        elif feedback.sentiment == "negative":
            response = "We're sorry about your experience. A live agent is addressing the issue."

        if feedback_language != "english":
            response = self.gemini_manager.translate_text(response, feedback_language)
        return f"{response}\nYour feedback: {feedback.message}"

    def escalate_to_agent(self, feedback: Feedback):
        client = Client(self.account_sid, self.auth_token)
        msg = self.gemini_manager._summarise_feedback(feedback.message)
        call = client.calls.create(
            twiml=f"<Response><Say>Customer {feedback.customer.first_name} left a negative review. Here's the summary: {msg}.Please review and assist.</Say></Response>",
            to=os.getenv("TEST_CALL_NUMBER"), # this should be customer number but currently testing with hardcoded number
            from_=self.twilio_phone_number,
        )
        logger.info(f"Call initiated to live agent: {call.sid}")
