# Telinga: Customer Feedback and Notification System
An interactive customer support API built with Django, Twilio (for SMS), Nylas (for Email & calendar events), and Google's Gemini AI for sentiment analysis and automated responses.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Setup](#setup)
- [Configuration](#configuration)
- [Admin Interface](#admin-interface)
- [Usage](#usage)
  - [Endpoints](#endpoints)
    - [Authentication](#authentication)
    - [Customer Management](#customer-management)
    - [Feedback and Notifications](#feedback-and-notifications)
    - [Email and Calendar Management](#email-and-calendar-management)
- [Nylas Integration](#nylas-integration)
- [Gemini AI Integration](#gemini-ai-integration)
- [Celery Tasks](#celery-tasks)
- [Logging](#logging)
- [Run Postman Collection](#run-collection)

## Overview

This project is a comprehensive system for handling customer feedback, notifications, and email management. It leverages Twilio for sending and receiving SMS, Nylas for email tracking and calendar events, Google's Gemini AI for natural language processing tasks, and Django with Celery for backend management and asynchronous tasks.

## Features

- **Customer Management**: Upload and manage customer data via CSV files.
- **Feedback Management**: Capture and analyze customer feedback via SMS and email.
- **Sentiment Analysis**: Analyze feedback sentiment using Google's Gemini AI.
- **Automated Notifications**: Send notifications and responses based on feedback sentiment.
- **Email Threading**: Track and analyze email threads for comprehensive customer interaction history.
- **Calendar Integration**: Schedule meetings and manage events based on customer interactions.
- **Multi-language Support**: Detect language and translate responses for global customer base.
- **Admin Interface**: Manage customers, feedback, and system settings through the Django admin interface.
- **Asynchronous Processing**: Use Celery for scheduling messages and background tasks.

## Setup

### Prerequisites

- Python 3.9+
- Django 4.2+
- Celery 5.0+
- Redis/Sqlite (for Celery broker)
- Twilio Account
- Nylas Account

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/Onwuagba/Telinga/.git
    cd Telinga
    git checkout develop  # code is in develop mode
    ```

2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

4. Apply migrations:
    ```sh
    python manage.py migrate
    ```

5. Create a superuser for the admin interface:
    ```sh
    python manage.py createsuperuser
    ```

6. Create a Nylas webhook for managing email replies:
    ```sh
    python manage.py create_nylas_webhook
    ```

### Running the Application

1. Start the Django development server:
    ```sh
    python manage.py runserver
    ```

2. Start the Celery worker:
    ```sh
    celery -A telinga worker -l info
    ```

3. Start the Celery beat scheduler:
    ```sh
    celery -A telinga beat -l info
    ```

## Configuration

### Environment Variables

Edit the `.env.copy` file and rename to `.env`

## Admin Interface
Access the Django admin interface to manage customers and feedback.

- URL: /admin/
- Credentials: Use the superuser credentials created during setup.
- Create a new user and assign API key via the API key model.


## Usage
### Endpoints
#### Authentication

1. **Register User**
Register a new business.
```
URL: /api/register/
Method: POST

Parameters:
username: User's username
email: User's email (optional)
password: User's password
```

2. **Get API Key**
Retrieve the API key for the authenticated user.

```
URL: /api/get_api_key/
Method: GET

Parameters:
username: User's username
password: User's password
```

3. **Change API Key**
Generate and update the API key for the authenticated user.

```
URL: /api/change_api_key/
Method: PUT

Headers:
Authorization: Token <your_token>
```

4. **Update Password**
Update the password for the authenticated user.

```
URL: /api/update-password/
Method: PUT

Headers:
Authorization: Token <your_token>

Parameters:
old_password: User's current password
new_password: User's new password
```

#### Customer Management

1. **Upload Customers**
    Upload a CSV file with customer data and schedule messages.

    ```
    URL: /upload-csv/
    Method: POST

    Parameters:
    csv_file: CSV file containing customer data
    message: Message template with placeholders
    delivery_time: Delivery time (now or ISO timestamp)
    ```
   Example:
   ```sh
   curl -X POST https://127.0.0.1:8000/upload-csv/ \
       -H "X-API-Key={{API-KEY}}" \
       -F "csv_file=@path/to/yourfile.csv" \
       -F "delivery_time=2024-06-18T00:18:00" \
       -F "message=Hello {{first_name}} {{last_name}}. Kindly confirm ..."
   ```

   Allowed placeholders: phone_number, email, first_name, last_name

#### Feedback and Notifications


1. **Twilio Webhook**
   Handle incoming feedback via Twilio SMS or email.

   ```
   URL: /twilio/webhook/
   Method: POST

   Parameters:
   From: Sender's phone number or email
   Body: Message content
   ```

    Example:
    ```sh
    curl -X POST https://127.0.0.1:8000/twilio/webhook/ \
        -d "From=+1234567890" \
        -d "Body=Your feedback message here"
    ```

#### Email and Calendar Management

1. **Get Email Threads**
   Retrieve a list of email threads.

   ```
   URL: /get-email-threads/
   Method: GET
   ```

2. **Analyze Email Thread**
   Analyze and summarize an email thread.

   ```
   URL: /analyze-email-thread/
   Method: POST

   Parameters:
   thread_id: ID of the email thread to analyze
   ```

3. **Schedule Meeting**
   Schedule a meeting with a customer.

   ```
   URL: /schedule-meeting/
   Method: POST

   Parameters:
   customer_id: ID of the customer
   suggested_time: Suggested time for the meeting
   title: Title of the meeting (optional)
   ```

## Nylas Integration

### Webhook Creation
Before using any Nylas features, you must create a webhook programmatically. This is done using the management command provided in this project.

1. **Create the Webhook**
    Run the management command to create the webhook (if you did not create the webhook):

    ```sh
    python manage.py create_nylas_webhook
    ```

    This command automatically generates the callback URL by appending `/nylas_webhook/` to your domain (set this in your env and use VS port forwarding to test locally).

2. **Webhook Usage**
    Once the webhook is created, Nylas will send events to the specified callback URL. You can process these events in your Django views.

3. **Nylas Events Tracked**
    The webhook tracks the following events:
    <!-- * `message.created`: Triggered when a new message is created. -->
    * `thread.replied`: Triggered when a participant replies to a tracked email thread.

### Nylas Features
- **Email Tracking**: Track email replies and trigger actions based on customer responses.
- **Email Thread Analysis**: Summarize and analyze email threads for quick context.
- **Calendar Management**: Schedule and manage meetings directly from the application.
- **Webhook Management**: Automatically create and manage webhooks for handling email interactions.

## Gemini AI Integration

The system uses Google's Gemini AI for various natural language processing tasks:

- **Sentiment Analysis**: Analyze the sentiment of customer feedback.
- **Email Subject Generation**: Generate relevant email subjects based on content.
- **Feedback Summarization**: Create concise summaries of customer feedback.
- **Language Detection**: Detect the language of incoming messages.
- **Translation**: Translate messages to ensure proper communication regardless of language barriers.
- **Email Draft Generation**: Create professional email drafts based on given contexts.
- **Meeting Time Suggestion**: Suggest appropriate meeting times based on email content.


## Celery Tasks

1. **Schedule Message**
   - Task Name: main.tasks.schedule_message
   - Parameters: customer_id (ID of the customer to send a message to)

2. **Check Delivery Status**
   - Task Name: main.tasks.check_delivery_status
   - Parameters: None


### Logging
Logs are configured to output to both console and file. You can configure this in the settings file

## run-collection

[<img src="https://run.pstmn.io/button.svg" alt="Run In Postman" style="width: 128px; height: 32px;">](https://app.getpostman.com/run-collection/7261954-9ca33fb4-8228-4520-a351-322910e08f28?action=collection%2Ffork&source=rip_markdown&collection-url=entityId%3D7261954-9ca33fb4-8228-4520-a351-322910e08f28%26entityType%3Dcollection%26workspaceId%3D21eb856b-3287-46ec-951c-824c21f61034)