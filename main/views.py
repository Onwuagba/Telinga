import csv
import io
import logging
import os
import re

from django.conf import settings
from django.template.defaultfilters import escape
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response

from main.api_response import CustomAPIResponse
from main.models import MessageFormat, Customer, Feedback
from main.serializers import CustomerSerializer
from main.tasks import schedule_message

load_dotenv()

logger = logging.getLogger("app")


# Create your views here.
class Home(APIView):
    def get(self, request, *args):
        user_name = request.user
        message = f"Welcome {user_name.username}"
        status_code = status.HTTP_200_OK
        status_msg = "success"

        return CustomAPIResponse(message, status_code, status_msg).send()


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
        allowed_placeholders = {f"{{{{{header}}}}}" for header in headers}
        placeholders = set(re.findall(r"{{\s*\w+\s*}}", message_format))

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
        headers = [header.strip() for header in headers if header.strip()]

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
                phone_number = row[0].strip() if len(row) > 0 else None
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
                    schedule_message.apply_async(args=[customer.id], countdown=0)
                else:
                    print(
                        f"sending message to {customer.first_name} at {delivery_time}"
                    )
                    schedule_message.apply_async(args=[customer.id], eta=delivery_time)

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
    http_method_names = ["post"]

    def post(self, request):
        from_number = request.POST.get("From")
        body = request.POST.get("Body")
        # to_number = request.POST.get("To")
        email = request.POST.get("Email")

        logger.info(f"Incoming feedback from {from_number or email}: {body}")

        # Find the customer by phone number or email
        customer = None
        if from_number:
            customer = Customer.objects.filter(phone_number=from_number).first()
        elif email:
            customer = Customer.objects.filter(email__iexact=email).first()

        if not customer:
            logger.error(f"No customer found for {from_number or email}")
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
