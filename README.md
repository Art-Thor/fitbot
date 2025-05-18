# FitBot

A Slack bot for managing fitness challenges, built with FastAPI, Celery, and PostgreSQL.

## Features

- Process fitness challenge submissions via Slack Workflow Builder
- OCR processing of screenshots for validation
- Asynchronous task processing with Celery
- PostgreSQL database for storing results
- Docker containerization for easy deployment
- Socket Mode for reliable Slack communication

## Prerequisites

- Docker and Docker Compose
- Slack App with Socket Mode enabled
- Tesseract OCR installed (included in Docker image)

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
WORKFLOW_BOT_ID=your-workflow-bot-id

# Challenge Channels
# Comma-separated list of Slack channel IDs where /challenge commands are allowed
# Example: CHALLENGE_CHANNELS=C08SM8NESGJ,C123ABC456D
# Leave empty to allow commands in any channel
CHALLENGE_CHANNELS=C08SM8NESGJ

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@db:5432/fitbot
REDIS_URL=redis://redis:6379/0

# Logging
LOG_LEVEL=DEBUG

# Metrics
METRICS_PORT=9000
```

## Running the Application

1. Build and start the containers:
```bash
docker-compose up --build
```

The application will automatically:
- Start the FastAPI server
- Initialize the database
- Start the Socket Mode handler for Slack communication
- Start the Celery worker for processing submissions

No additional setup is required - the bot will be ready to use as soon as the containers are up.

## Architecture

- `app/main.py`: FastAPI application with Socket Mode handler
- `app/slack_app.py`: Slack Bolt app with all event handlers
- `app/workflow_handler.py`: Handles messages from Workflow Bot
- `app/tasks.py`: Celery tasks for processing submissions
- `app/utils/ocr.py`: OCR processing for screenshots
- `app/utils/parsing.py`: Metric parsing utilities
- `app/models/`: SQLAlchemy models for database
- `app/database.py`: Database connection and session management

## Development

The application uses:
- FastAPI for the web server
- Slack Bolt for Slack integration
- Celery for async task processing
- Redis for message broker
- PostgreSQL for data storage
- Tesseract for OCR processing
- Docker for containerization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 