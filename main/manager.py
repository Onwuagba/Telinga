import logging, os
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv

import google.generativeai as genai
from twilio.rest import Client

from main.models import Feedback

load_dotenv()

genai.configure(api_key=os.getenv("TW_GEMINI_API_KEY"))
logger = logging.getLogger("app")


class GeminiManager:
    def __init__(self) -> None:
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _generate_response(self, prompt):
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Error generating response"

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
        return self._generate_response(prompt)

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
        return self._generate_response(prompt)


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
                value = getattr(customer, header, "")
                parsed_message = parsed_message.replace(placeholder, value)
            else:
                logging.error(
                    f"Placeholder {placeholder} not found in the message format"
                )
        return parsed_message

    def respond_to_feedback(self, feedback: Feedback):
        customer = feedback.customer
        logging.info(f"Responding to user feedback from {customer.first_name}")
        message = self.generate_response_message(feedback)
        if feedback.source == "sms":
            logging.info(f"Feedback from {feedback.customer.first_name} sent via SMS")
            self.send_sms(customer.phone_number, message)
        elif feedback.source == "email":
            logging.info(f"Feedback from {feedback.customer.first_name} sent via email")
            subject = self.generate_email_subject(message)
            self.send_email(customer.email, subject, message)

    def generate_response_message(self, feedback: Feedback):
        if feedback.sentiment == "positive":
            return "Thank you for your positive feedback! We appreciate your support."
        elif feedback.sentiment == "neutral":
            return "Thank you for your feedback. They are noted and will be taken into consideration"
        elif feedback.sentiment == "negative":
            return (
                "We're sorry to hear about your experience. "
                "Your issue has been escalated to a live agent and is receiving attention."
            )

    def escalate_to_agent(self, feedback: Feedback):
        client = Client(self.account_sid, self.auth_token)
        msg = self.gemini_manager._summarise_feedback(feedback.message)
        call = client.calls.create(
            twiml=f"<Response><Say>Customer {feedback.customer.first_name} left a negative review. \n**Summary: {msg}\n**Source: {feedback.source}\nPlease review and assist.</Say></Response>",
            to="agent_phone_number",
            from_=self.twilio_phone_number,
        )
        logger.info(f"Call initiated to live agent: {call.sid}")
