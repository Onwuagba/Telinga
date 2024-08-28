import logging
import os
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import google.generativeai as genai
from twilio.rest import Client
from nylas import Client as nyClient

from main.models import Feedback, MessageStatus

load_dotenv()

genai.configure(api_key=os.getenv("TW_GEMINI_API_KEY"))
logger = logging.getLogger("app")

nylas_client = nyClient(
    os.getenv('NYLAS_API_KEY'),
    os.getenv('NYLAS_API_URI')
)
nylas_grant = os.getenv('NYLAS_GRANT_ID')


class GeminiManager:
    def __init__(self) -> None:
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _generate_response(self, prompt, message=None):
        try:
            response = self.model.generate_content(prompt)
            if response.parts:
                return response.parts[0].text.strip()
            else:
                logger.error(
                    f"No valid parts in the response. {response}")
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
        # Technique: Zero-shot with clear constraints
        prompt = f"Generate a concise email subject for the following message. Output the subject line only, without any additional text or explanation:\n\n{message}"
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
        # Technique: Few-shot learning with structured output
        prompt = f"""Analyze the sentiment of the following feedback. Respond with only one word: 'positive', 'negative', or 'neutral'.

Examples:
Feedback: "I love this product!"
Sentiment: positive

Feedback: "This service is terrible."
Sentiment: negative

Feedback: "It's okay, nothing special."
Sentiment: neutral

Feedback: "{feedback}"
Sentiment:"""
        result = self._generate_response(prompt).lower()

        if result in ["positive", "negative", "neutral"]:
            return result
        else:
            logger.error(
                f"Unexpected sentiment analysis result: {result}")
            return "neutral"

    def _summarise_feedback(self, feedback):
        logger.info("Summarising feedback...")
        # Technique: Specific instructions with output constraints
        prompt = f"""Summarize the following feedback in exactly two sentences. Ensure the summary is concise and captures the main points:

Feedback: {feedback}

Summary:"""
        return self._generate_response(prompt, feedback[:20])

    def detect_language(self, text):
        logger.info("Detecting language...")
        # Technique: One-shot learning with explicit formatting
        prompt = f"""Detect the language of the following text. Respond with the language name in lowercase, without any additional text.

Example:
Text: "Bonjour, comment allez-vous?"
Language: french

Text: "{text}"
Language:"""
        detected_language = self._generate_response(prompt)
        logger.info(f"detected_language: {detected_language}")
        return detected_language.strip().lower()

    def translate_text(self, text, target_language="en"):
        detected_language = self.detect_language(text)
        logger.info(
            f"Translating text from {detected_language} to {target_language}..."
        )
        # Technique: Task decomposition with clear instructions
        prompt = f"""Translate the following text from {detected_language} to {target_language}. Provide only the translated text without any explanations or additional information.

Original text: {text}

Translated text:"""
        translated_text = self._generate_response(prompt, text[:20])
        return translated_text

    def generate_email_draft(self, subject, body):
        """Generate an email draft using Gemini AI"""
        prompt = f"Generate a professional email draft with the following subject: '{subject}' and main points: {body}"
        return self._generate_response(prompt)

    def suggest_meeting_time(self, email_body):
        """Suggest a meeting time based on email content"""
        prompt = f"Based on the following email content, suggest an appropriate meeting time: {email_body}"
        return self._generate_response(prompt)


class CustomerNotificationManager:
    def __init__(self, account_sid, auth_token, twilio_phone_number, email_from):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.twilio_phone_number = twilio_phone_number
        self.email_from = email_from
        self.gemini_manager = GeminiManager()  # Instantiate GeminiManager
        self.nylas_client = nylas_client

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
        logger.info(
            f"Notification service called by {customer.first_name} for business `{customer.message_format.business.username}`"
        )
        if customer.phone_number:
            logger.info(
                f"{customer.first_name} has a phone number {customer.phone_number}"
            )
            message_sid = self.send_sms(
                f"+{customer.phone_number}",
                self.parse_message(
                    customer.message_format.message, customer),
            )
            logger.info(
                f"Notification to {customer.first_name} completed")

            # Save message status
            MessageStatus.objects.create(
                customer=customer, message_sid=message_sid, status="queued"
            )
        elif customer.email:
            logger.info(
                f"{customer.first_name} has email address {customer.email}")
            subject = self.generate_email_subject(
                customer.message_format.message)
            if self.send_email_nylas(
                customer.email,
                subject,
                self.parse_message(
                    customer.message_format.message, customer),
            ):
                logger.info(
                    f"Notification to {customer.first_name} completed")
            # kene: add retry logic later
            logger.error(
                f"Notification to {customer.first_name} failed to complete")
        else:
            logger.error(
                "Customer does not have a phone number or email")

    def send_sms(self, phone_number, message):
        logger.info(f"Sending SMS to phone number {phone_number}")
        # exception is raised in celery allowing it to fail & retry when necessary
        client = Client(self.account_sid, self.auth_token)
        if "+" not in phone_number:
            phone_number = f"+{phone_number}"
        message = client.messages.create(
            body=message, from_=self.twilio_phone_number, to=phone_number
        )
        logger.info(f"SMS sent to {phone_number}: {message.sid}")

        return message.sid

    def send_email(self, email, subject, message):
        logger.info(f"Sending email to {email}")
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
        logger.info(f"Parsing message for {customer.first_name}")
        parsed_message = message_format
        for header in settings.CSV_REQUIRED_HEADERS:
            placeholder = f"{{{{{header}}}}}".strip()

            if placeholder in parsed_message:
                value = getattr(customer, header, "")
                parsed_message = parsed_message.replace(
                    placeholder, value)

        return parsed_message

    def respond_to_feedback(self, feedback: Feedback):
        customer = feedback.customer
        logger.info(
            f"Responding to user feedback from {customer.first_name}")
        message = self.generate_response_message(feedback)
        try:
            if feedback.source == "sms":
                logger.info(
                    f"Feedback from {feedback.customer.first_name} sent via SMS"
                )
                self.send_sms(customer.phone_number, message)
            elif feedback.source == "email":
                logger.info(
                    f"Feedback from {feedback.customer.first_name} sent via email"
                )
                subject = self.generate_email_subject(message)
                self.send_email_nylas(
                    customer.email, subject, message)
        except Exception as e:
            logger.error(f"Error sending response to customer: {e}")

    def generate_response_message(self, feedback: Feedback):
        feedback_language = self.gemini_manager.detect_language(
            feedback.message)
        print(f"Print: Sentiment is {feedback.sentiment}")
        logger.info(f"Sentiment is {feedback.sentiment}")

        if feedback.sentiment == "positive":
            response = (
                "Thank you for your positive feedback! We appreciate your support."
            )
        elif feedback.sentiment == "neutral":
            response = "Thank you for your feedback. They are noted and will be taken into consideration"
        elif feedback.sentiment == "negative":
            if feedback.source == "sms":
                response = "We're sorry about your experience. A live agent is addressing the issue."
            else:
                response = self.gemini_manager.generate_email_draft(
                    "Addressing Your Concerns",
                    f"Apologize and address the following feedback: {feedback.message}"
                )
        else:
            response = "Thank you for your feedback"

        if feedback_language != "english":
            response = self.gemini_manager.translate_text(
                response, feedback_language)

        return f"{response}\nFeedback: {feedback.message}"

    def escalate_to_agent(self, feedback: Feedback):
        feedback_language = self.gemini_manager.detect_language(
            feedback.message)
        title = "Feedback review with"

        if feedback.source == "sms":
            # initiate call to customer
            client = Client(self.account_sid, self.auth_token)
            msg = self.gemini_manager._summarise_feedback(
                feedback.message)
            call = client.calls.create(
                twiml=f"<Response><Say>Customer {feedback.customer.first_name} left a negative review. Here's the summary: {msg}.Please review and assist.</Say></Response>",
                to=os.getenv(
                    "TEST_CALL_NUMBER"
                ),  # this should be customer number but currently testing with hardcoded number
                from_=self.twilio_phone_number,
            )
            logger.info(f"Call initiated to live agent: {call.sid}")
        else:
            if feedback_language != "english":
                title = self.gemini_manager.translate_text(
                    title, feedback_language)

            # Suggest a meeting time
            suggested_time = self.gemini_manager.suggest_meeting_time(
                feedback.message)
            # schedule meeting with customer
            self.schedule_meeting(
                feedback.customer, suggested_time, title)

    def send_email_nylas(self, to_email, subject, body):
        try:
            draft = self.nylas_client.drafts.create(
                nylas_grant,
                request_body={
                    "to": [{'email': to_email}],
                    "reply_to": [{"email": self.email_from}],
                    "subject": subject,
                    "body": body,
                }
            )
            draft.send(
                nylas_grant,
                draft)
            logger.info(f"Email sent via Nylas to {to_email}")
            return True
        except Exception as e:
            logger.error(
                f"Error sending email via Nylas: {str(e.args[0])}")
            return False

    def schedule_meeting(self, customer, suggested_time, title):
        """
        Schedules a meeting on the default calendar using the provided customer object and suggested time.

        Args:
            customer (Customer): The customer object for whom the meeting is being scheduled.
            suggested_time (datetime): The suggested time for the meeting.
            title (str): A title for the meeting.

        Returns:
            bool: True if the meeting is scheduled, False otherwise.
        """
        try:
            calendar_id = self.get_calendar_id()
            event = self.nylas_client.events.create(
                nylas_grant,
                request_body={
                    "title": f"Telinga: {title} {customer.first_name} {customer.last_name}",
                    "when": {'start_time': suggested_time,
                             'end_time': suggested_time + 3600}  # 1 hour meeting,
                },
                query_params={
                    "calendar_id": calendar_id
                }
            )

            # update meeting with customer email
            self.nylas_client.events.update(
                nylas_grant,
                event,
                request_body={
                    "participants": [{"name": f"{customer.first_name} {customer.last_name}", 'email': customer.email}],
                    "notify_participants": "true"
                },
                query_params={
                    "calendar_id": calendar_id
                }
            )

            logger.info(
                f"Meeting scheduled with {customer.email} at {suggested_time}")
            return True
        except Exception as e:
            logger.error(f"Error scheduling meeting: {e}")
            return False

    def analyze_email_thread(self, thread_id):
        thread = self.nylas_client.threads.get(thread_id)
        messages = thread.messages
        combined_content = " ".join([msg.body for msg in messages])
        summary = self.gemini_manager._summarise_feedback(
            combined_content)
        return summary

    def get_calendar_id(self):
        # just return the first id which is often the user email for Google Calendar
        return next((c.id for c in nylas_client.calendars.list(nylas_grant)[0]), None)
