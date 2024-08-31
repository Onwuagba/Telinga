import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model, authenticate
from django.db import IntegrityError
from django.http import HttpResponse
from django.template.defaultfilters import escape
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from twilio.request_validator import RequestValidator

from main.api_response import CustomAPIResponse
from main.manager import nylas_client, nylas_grant
from main.models import APIKey, MessageFormat, Customer, Feedback, MessageStatus, NylasWebhook
from main.serializers import (
    APIKeySerializer,
    CustomerSerializer,
    UpdatePasswordSerializer,
    UserSerializer,
)
from main.tasks import schedule_message
from main.utils import message_manager, nylas_client

load_dotenv()

logger = logging.getLogger("app")
User = get_user_model()


# Create your views here.
class Home(APIView):
    def get(self, request, *args):
        user_name = request.user
        message = f"Welcome {user_name.username}"
        status_code = status.HTTP_200_OK
        status_msg = "success"

        return CustomAPIResponse(message, status_code, status_msg).send()


class UserRegistrationView(CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = UserSerializer
    http_method_names = ["post"]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            message = "Registration successful."
            status_code = status.HTTP_201_CREATED
            code_status = "success"
        except Exception as e:
            logger.error(
                f"Exception in registration. Email {request.data.get('email')}: {e}"
            )
            message = e.args[0]
            status_code = status.HTTP_400_BAD_REQUEST
            code_status = "failed"

        response = CustomAPIResponse(
            message, status_code, code_status)
        return response.send()


class APIKeyView(RetrieveAPIView):
    serializer_class = APIKeySerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def post(self, request):
        message = "Invalid credentials"
        status_code = status.HTTP_400_BAD_REQUEST
        code_status = "failed"

        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)

        if user is not None:
            # Attempt to get an existing APIKey or create a new one with a unique key
            while True:
                try:
                    api_key, created = APIKey.objects.get_or_create(
                        business=user)
                    if created:
                        api_key.key = secrets.token_urlsafe(40)
                        api_key.save()
                    serializer = APIKeySerializer(api_key)
                    message = serializer.data
                    status_code = status.HTTP_200_OK
                    code_status = "success"
                    break  # Exit the loop if successful
                except IntegrityError:
                    logger.error(
                        "Integrity error while trying to create api key")
                    # Handle the case where the generated key already exists
                    continue

        response = CustomAPIResponse(
            message, status_code, code_status)
        return response.send()


class ChangeAPIKeyView(APIView):
    http_method_names = ["put"]

    def put(self, request, *args, **kwargs):
        user = request.user

        new_api_key = secrets.token_urlsafe(40)

        try:
            business_key = user.business_key
        except APIKey.DoesNotExist:
            # Handle case where related APIKey does not exist
            business_key = APIKey.objects.create(
                user=user, key=new_api_key)

        business_key.key = new_api_key
        business_key.save()

        return Response({"api_key": new_api_key}, status=status.HTTP_200_OK)


class UpdatePasswordView(APIView):
    serializer_class = UpdatePasswordSerializer
    http_method_names = ["put"]

    def put(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        try:
            serializer.is_valid(raise_exception=True)
            serializer.update(request.user, serializer.validated_data)
            message = "Password updated successfully."
            status_code = status.HTTP_200_OK
            code_status = "success"
        except ValidationError as e:
            message = e.detail
            status_code = status.HTTP_400_BAD_REQUEST
            code_status = "failed"
        except Exception as e:
            logger.error(f"Exception in updating password: {e}")
            message = "Failed to update password."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            code_status = "failed"

        response_data = {
            "message": message,
            "status_code": status_code,
            "code_status": code_status,
        }
        return Response(response_data, status=status_code)


class UploadCustomerView(APIView):
    parser_classes = [
        MultiPartParser,
        JSONParser,
    ]
    http_method_names = ["post"]

    def validate_and_sanitize_message_format(self, message_format, headers):
        """
        Validate and sanitize the message format.

        Args:
            message_format (str): The message format to be validated and sanitized.
            headers (List[str]): The headers of the CSV file.

        Returns:
            str or None: The sanitized message format if all placeholders are allowed,
                         None otherwise.

        Raises:
            None

        Description:
            This function validates the message format by checking if all placeholders
            in the message format are allowed. It creates a regex pattern for allowed
            placeholders and checks if all placeholders in the message format are
            present in the allowed placeholders. If any placeholder is not allowed,
            an error is logged and None is returned. If all placeholders are allowed,
            the entire message format is sanitized by escaping any special characters
            and returned.
        """

        # Create a regex pattern for allowed placeholders
        allowed_placeholders = {
            f"{{{{{header}}}}}" for header in headers}
        placeholders = set(re.findall(
            r"{{\s*\w+\s*}}", message_format))

        # Check if all placeholders in the message format are allowed
        if not placeholders.issubset(allowed_placeholders):
            logger.error(
                f"Invalid placeholders in message format. Uploaded placeholders: {placeholders}"
            )
            return None

        # Sanitize the entire message format
        sanitized_message_format = escape(message_format)
        return sanitized_message_format

    def validate_headers(self, headers):
        """
        Validates the headers of a CSV file.

        Args:
            headers (List[str]): The headers of the CSV file.

        Returns:
            bool: True if the headers are valid, False otherwise.
        """
        headers = [header.strip()
                   for header in headers if header.strip()]

        if headers != settings.CSV_REQUIRED_HEADERS:
            logger.error(
                f"Invalid CSV headers: {headers}. Required: {settings.CSV_REQUIRED_HEADERS}"
            )
            return False
        return True

    def post(self, request):
        """
        Handles the HTTP POST request to upload a CSV file.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: The HTTP response object.

        Raises:
            CSVError: If there is an error parsing the CSV file.
            Exception: If there is an error processing the CSV file.

        This function first retrieves the uploaded CSV file and the accompanying message from the request.
        It then performs several validations on the file, including checking the file extension, MIME type, and size.
        Next, it reads and processes the CSV file, validating the headers and each row of data.
        If any validation errors occur, they are added to a list of errors and returned in the response.
        If all data is valid, it is saved to the database and a success message is returned.
        If there is an error parsing or processing the CSV file, an appropriate error response is returned.
        """

        logger.debug(
            f"Received request to upload CSV file from user: {request.user.username}"
        )
        csv_file = request.FILES.get("csv_file")
        message_format = request.data.get("message")
        delivery_time = request.data.get("delivery_time")
        print(timezone.now())

        if not csv_file:
            return CustomAPIResponse(
                "No CSV file uploaded", status.HTTP_400_BAD_REQUEST, "failed"
            ).send()

        if not message_format:
            return CustomAPIResponse(
                "No accompanying message provided",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()

        # Validate file extension
        file_extension = os.path.splitext(csv_file.name)[1].lower()
        if file_extension != ".csv":
            logger.error(
                f"Invalid file type: {file_extension} from user {request.user.username}"
            )
            return CustomAPIResponse(
                "Invalid file type. Only CSV files allowed",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()

        # Check the MIME type
        if csv_file.content_type != "text/csv":
            logger.error(
                f"Invalid MIME type: {csv_file.content_type} from user {request.user.username}"
            )
            return CustomAPIResponse(
                "File type is not csv",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()

        # Validate file size (limit to 5MB)
        if csv_file.size > int(settings.MAX_UPLOAD_FILE_SIZE):
            logger.error(
                f"File size exceeds limit. CSV size: {csv_file.size} | Max file size: {settings.MAX_UPLOAD_FILE_SIZE} bytes"
            )
            return CustomAPIResponse(
                f"File size exceeds the allowed limit of {settings.MAX_UPLOAD_FILE_SIZE} bytes",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()

        try:
            delivery_time = (
                timezone.datetime.fromisoformat(delivery_time)
                if delivery_time
                else "now"
            )  # default to now
            print(delivery_time)

            # Read and process the file
            logger.debug(f"Reading CSV file {csv_file.name}")
            file_data = csv_file.read().decode("utf-8")
            io_string = io.StringIO(file_data)
            reader = csv.reader(io_string)
            headers = next(reader)  # read header row

            # Validate headers
            if not self.validate_headers(headers):
                return CustomAPIResponse(
                    f"Invalid CSV headers. Required: {settings.CSV_REQUIRED_HEADERS}",
                    status.HTTP_400_BAD_REQUEST,
                    "failed",
                ).send()

            # Validate and sanitize the message
            sanitized_message_format = None
            if message_format:
                sanitized_message_format = self.validate_and_sanitize_message_format(
                    message_format, headers
                )

            if not sanitized_message_format:
                return CustomAPIResponse(
                    f"Invalid message. Allowed placeholders {headers}",
                    status.HTTP_400_BAD_REQUEST,
                    "failed",
                ).send()

            message_object, _ = MessageFormat.objects.get_or_create(
                message=sanitized_message_format, business=request.user
            )

            errors = []
            for row_number, row in enumerate(
                reader, start=1
            ):  # Start from 1 to account for the skipped header
                # Sanitize and validate input data
                phone_number = row[0].strip() if len(
                    row) > 0 else None
                email = row[1].strip() if len(row) > 1 else None
                first_name = row[2].strip() if len(row) > 2 else None
                last_name = row[3].strip() if len(row) > 3 else None

                customer_data = {
                    "phone_number": phone_number,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "message_format": message_object.pk,
                }

                # Ensure email and phone number are not both null
                if not phone_number and not email:
                    logger.warning(
                        f"Row {row_number + 1}: Phone number and email cannot both be null"
                    )
                    errors.append(
                        {
                            "error": [
                                "Phone number and email cannot both be null"
                            ],  # list cos of serializer.errors below
                            "row_number": row_number + 1,
                        }  # Adding 1 to row_number to account for the header row
                    )
                    continue

                serializer = CustomerSerializer(data=customer_data)
                if not serializer.is_valid():
                    logger.warning(
                        f"Row {row_number + 1}: Validation error - {serializer.errors}"
                    )
                    error = serializer.errors
                    error["row_number"] = row_number + 1
                    errors.append(error)
                    continue

                # Save valid data
                customer = serializer.save()

                # Schedule or trigger message delivery
                if delivery_time == "now":
                    print("sending message to celery now")
                    schedule_message.apply_async(
                        args=[customer.id], countdown=0)
                else:
                    print(
                        f"sending message to {customer.first_name} at {delivery_time}"
                    )
                    schedule_message.apply_async(
                        args=[customer.id], eta=delivery_time)

            if errors:
                return CustomAPIResponse(
                    errors,
                    status.HTTP_400_BAD_REQUEST,
                    "failed",
                ).send()

            logger.debug("CSV file processed successfully")
            return CustomAPIResponse(
                "Customers uploaded successfully!",
                status.HTTP_201_CREATED,
                "success",
            ).send()

        except csv.Error as e:
            logger.error(f"CSV parsing error: {e}")
            return CustomAPIResponse(
                f"CSV parsing error: {e}",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()
        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            return CustomAPIResponse(
                f"Error processing CSV: {e}",
                status.HTTP_400_BAD_REQUEST,
                "failed",
            ).send()


@method_decorator(csrf_exempt, name="dispatch")
class TwilioWebhookView(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def post(self, request):
        # Validate incoming Twilio request
        validator = RequestValidator(settings.AUTH_TOKEN)
        signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")

        url = request.build_absolute_uri()
        post_vars = request.POST.dict()

        validate_request = validator.validate(
            url, post_vars, signature)
        print("Twilio validation returned ", validate_request)

        if not validator.validate(url, post_vars, signature) and not settings.DEBUG:
            logger.info(
                f"validation failed for incoming webhook from {from_number or email}: {body}"
            )
            return Response(
                {"error": "Invalid request"}, status=status.HTTP_403_FORBIDDEN
            )

        from_number = request.POST.get("From")
        body = request.POST.get("Body")
        # to_number = request.POST.get("To")
        email = request.POST.get("Email")

        logger.info(
            f"Incoming webhook feedback from {from_number or email}: {body}")

        # Find the customer by phone number or email
        customer = None
        if from_number:
            if "+" in from_number:
                from_number = str(from_number).replace("+", "")
            customer = Customer.objects.filter(
                phone_number=from_number).first()
        elif email:
            customer = Customer.objects.filter(
                email__iexact=email).first()

        if not customer:
            logger.error(
                f"No customer found for {from_number or email}")
            return Response(
                {"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Save the feedback
        feedback = Feedback(
            customer=customer, message=body, source="sms" if from_number else "email"
        )
        feedback.save()

        # post-save signal is triggered to analyse sentiment and  respond to feedback

        return Response({"message": "Feedback processed"}, status=status.HTTP_200_OK)


# NYLAS VIEWS
class GetEmailThreadsView(APIView):
    http_method_names = ["get"]

    def get(self, request):
        try:
            threads = nylas_client.threads.list()
            data = [{"id": t.id, "subject": t.subject}
                    for t in threads]
            return CustomAPIResponse(data, status.HTTP_200_OK, "success").send()
        except Exception as e:
            return CustomAPIResponse(
                str(e), status.HTTP_500_INTERNAL_SERVER_ERROR, "failed"
            ).send()


class AnalyzeEmailThreadView(APIView):
    http_method_names = ["post"]

    def post(self, request):
        try:
            thread_id = request.data.get("thread_id")
            if not thread_id:
                return CustomAPIResponse(
                    "Thread ID is required", status.HTTP_400_BAD_REQUEST, "failed"
                ).send()

            summary = message_manager.analyze_email_thread(thread_id)
            return CustomAPIResponse(
                {"summary": summary}, status.HTTP_200_OK, "success"
            ).send()
        except Exception as e:
            return CustomAPIResponse(
                str(e), status.HTTP_500_INTERNAL_SERVER_ERROR, "failed"
            ).send()


class ScheduleMeetingView(APIView):
    http_method_names = ["post"]

    def post(self, request):
        try:
            customer_id = request.data.get("customer_id")
            suggested_time = request.data.get("suggested_time")
            title = request.data.get(
                "title") or "Review Meeting"

            if not customer_id or not suggested_time:
                return CustomAPIResponse(
                    "Customer ID and suggested time are required",
                    status.HTTP_400_BAD_REQUEST,
                    "failed",
                ).send()

            customer = Customer.objects.get(id=customer_id)
            message_manager.schedule_meeting(
                customer, suggested_time, title
            )
            return CustomAPIResponse(
                "Meeting scheduled successfully", status.HTTP_200_OK, "success"
            ).send()
        except Customer.DoesNotExist:
            return CustomAPIResponse(
                "Customer not found", status.HTTP_404_NOT_FOUND, "failed"
            ).send()
        except Exception as e:
            return CustomAPIResponse(
                str(e), status.HTTP_500_INTERNAL_SERVER_ERROR, "failed"
            ).send()


@method_decorator(csrf_exempt, name="dispatch")
class NylasWebhookView(APIView):
    permission_classes = (AllowAny,)
    http_method_names = ["get", "post"]

    def get(self, request, *args, **kwargs):
        # Handle the webhook verification GET request
        challenge = request.GET.get("challenge")
        if challenge:
            return HttpResponse(challenge, content_type="text/plain", status=200)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        logger.info('Nylas Webhook call starting...')
        try:
            # Validate the webhook signature
            signature = request.headers.get('X-Nylas-Signature')
            secret_key = self.get_secret_key()

            if not self.validate_signature(signature, secret_key, request.body):
                logger.error("Invalid webhook signature.")
                return Response({"error": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

            event = json.loads(request.body)

            if event.get("type") == "thread.replied":
                self.handle_thread_replied(event["data"])

            return Response({"status": "success"}, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def validate_signature(signature, secret_key, payload):
        computed_signature = hmac.new(
            key=secret_key.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, computed_signature)

    @staticmethod
    def get_secret_key():
        try:
            webhook = NylasWebhook.objects.get(
                trigger_type='thread.replied')
            return webhook.secret_key if webhook else settings.NYLAS_CLIENT_SECRET
        except NylasWebhook.DoesNotExist:
            return settings.NYLAS_CLIENT_SECRET

    def handle_thread_replied(self, data):
        # Retrieve the message details from the event data
        reply_message_id = data["object"]["message_id"]
        root_message_id = data["object"]["root_message_id"]
        logger.info(
            f"Reply Id: {reply_message_id}, Message Id: {root_message_id}")

        try:
            # Retrieve the original message status using the root_message_id
            sent_email = MessageStatus.objects.get(
                message_sid=root_message_id)
            customer = sent_email.customer

            # Retrieve the reply message using Nylas SDK
            reply_message = nylas_client.messages.find(
                os.getenv("NYLAS_GRANT_ID"), reply_message_id
            )

            self.process_customer_reply(reply_message, customer)

        except MessageStatus.DoesNotExist:
            logger.warning(
                f"No matching sent email found for root_message_id {root_message_id}"
            )
        except Exception as e:
            logger.error(f"Error processing thread reply: {e}")

    def process_customer_reply(self, message, customer: Customer):
        logger.info(f"Processing reply from {customer.email}")

        Feedback.objects.create(
            customer=customer,
            message=message[0].body,
            source="email"
        )

        # Log the reply
        logger.info(f"Reply from {customer.email}: {message.body}")
