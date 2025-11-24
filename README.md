# Geolocation Voucher System (Core)

## Project Context

This repository contains the core of a geolocation voucher application I architected for a startup. The project was originally deployed to production serving real users.

Note: This is a sanitized version of the original codebase. Branding, proprietary assets, and commit history have been removed to protect commercial IP. The logic has been altered slightly to ensure compatibility with local runs. The code demonstrates my work with Flask, SQLAlchemy, AWS, and Redis.

## Overview

This application allows users to discover vouchers based on their real-time geolocation. It features a secure redemption workflow using dynamic QR codes, rate limiting to prevent abuse, and high-performance geospatial querying.

The system was designed to handle horizontal scaling via AWS ECS and relies on a stateless backend architecture.

## Architecture & Tech Stack

Backend: Python, Flask (RESTful API & Server-Side Rendering)

Database: PostgreSQL (Production), SQLite (Dev)

Caching: Redis (Used for rate limiting & QR storage)

Infrastructure: AWS ECS/Fargate (Containerized deployment behind an ALB)

Observability: CloudWatch & Sentry (Distributed logging and error tracking)


## Key Features

1. Geospatial Search: Efficiently queries stores within a specific radius.

2. Dynamic QR Redemption: Generates unique, time-sensitive QR codes for voucher redemption.

3. Rate Limiting: Implements Flask-Limiter with Redis to protect API endpoints from abuse.

4. Production-Ready Logging: Integrated with watchtower for CloudWatch logging and Sentry for error tracking.

## Setup & Running Locally

Follow these steps to get the application running on your local machine.

1. Create Environment

```python -m venv venv```


2. Activate

Windows: 
```venv\Scripts\activate```
Mac/Linux: 
```source venv/bin/activate```

3. Install Dependencies

```pip install -r requirements.txt```


## Configuration
A .env file is included with default settings for local development.

Note: The app checks for AWS keys but handles missing keys gracefully for local testing.

## Database
The application uses a local SQLite database (development.db) by default. It will automatically initialize the schema on the first run. For the app to work, a store must be present in the DB with a location near the user. After running the app for the first time, you can run the file below to automatically do this
```python update_store_location.py```

## Run

Because the application requires a database entry within a certain distance from the user, first run: 
```python update_store_location.py```
This will attempt to fetch the users location and update the first DB entry to match.

Then:
```python run.py```


The application will start at http://127.0.0.1:5000.

## Developer Notes

Redis Fallback: The application attempts to connect to a Redis instance for rate limiting. If Redis is not detected locally, it automatically falls back to in-memory storage. You do not need Docker running to test the app.
