
# Telinga: Customer Feedback and Notification System
An interactive customer support API built with Django, Twilio, and Gemini AI for sentiment analysis and automated responses.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Setup](#setup)
- [Configuration](#configuration)
- [Admin Interface](#admin-interface)
- [Usage](#usage)
  - [Endpoints](#endpoints)
  - [Celery Tasks](#celery-tasks)
- [Run Postman Collection](#run-collection)

## Overview

This project is a comprehensive system for handling customer feedback and notifications. It leverages Twilio for sending and receiving SMS and emails, as well as Django and Celery for backend management and asynchronous tasks.

## Features

- **Customer Feedback Management**: Capture and analyze customer feedback via SMS and email.
- **Sentiment Analysis**: Analyze feedback sentiment using the `Gemini AI API`.
- **Automated Notifications**: Send notifications and responses based on feedback sentiment.
- **Twilio Integration**: Use Twilio for SMS and email communication.
- **Admin Interface**: Manage customers and feedback through the Django admin interface.
- **Celery Tasks**: Schedule and manage background tasks for sending messages and checking delivery status.

## Setup

### Prerequisites

- Python 3.9+
- Django 4.2+
- Celery 5.0+
- Redis/Sqlite (for Celery broker)
- Twilio Account

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
1. **Twilio Webhook**
Handle incoming feedback via Twilio SMS or email.

```
URL: /twilio/webhook/
Method: POST

Parameters:
From: Sender's phone number
Body: Message content
Email: Sender's email (optional)
```
Example:
```sh
curl -X POST https://127.0.0.1:8000/twilio/webhook/ \
    -d "From=+1234567890" \
    -d "Body=Your feedback message here"
```

2. **Customer Upload**
Upload a CSV file with customer data and schedule messages.

```
URL: /upload-csv/
Method: POST

Parameters:
csv_file: CSV file containing customer data
delivery_time: Delivery time (now or ISO timestamp)
```
Example:
```sh
curl -X POST https://127.0.0.1:8000/upload-csv/ \
    -H "X-API-Key={{API-KEY}}" \
    -F "csv_file=@path/to/yourfile.csv" \
    -F "delivery_time=2024-06-18T00:18:00"
    -F "message=Hello {{first_name}} {{last_name}}. Kindly confirm ..." # with placeholders.
    
    # Allowed placeholders: phone_number,email,first_name,last_name
```

### Celery Tasks
1. Schedule Message
    - Task Name: main.tasks.schedule_message
    - Parameters: <br> customer_id: ID of the customer to send a message to
2. Check Delivery Status
    - Task Name: main.tasks.check_delivery_status
    - Parameters: None

### Logging
Logs are configured to output to both console and file. You can configure this in the settings file

## run-collection

[<img src="https://run.pstmn.io/button.svg" alt="Run In Postman" style="width: 128px; height: 32px;">](https://app.getpostman.com/run-collection/7261954-9ca33fb4-8228-4520-a351-322910e08f28?action=collection%2Ffork&source=rip_markdown&collection-url=entityId%3D7261954-9ca33fb4-8228-4520-a351-322910e08f28%26entityType%3Dcollection%26workspaceId%3D21eb856b-3287-46ec-951c-824c21f61034)