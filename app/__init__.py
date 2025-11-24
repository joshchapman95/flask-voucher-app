import logging
import os
from datetime import datetime

import boto3
import redis
import sentry_sdk
import watchtower
from botocore.exceptions import ClientError, NoCredentialsError
from flask import Flask, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config


db = SQLAlchemy()
migrate = Migrate()
limiter = None


def setup_cloudwatch_logging(app):
    """Set up CloudWatch logging."""
    try:
        # Generate a stream name based on date and EC2 instance ID
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        try:
            # Safe fetch for instance ID
            instance_id = boto3.utils.InstanceMetadataFetcher().get_instance_identity()[
                "instanceId"
            ]
        except Exception:
            instance_id = "unknown"

        stream_name = f"{date_str}-{instance_id}"

        # Set up logging to CloudWatch
        cloudwatch_handler = watchtower.CloudWatchLogHandler(
            log_group="/ec2/myapp",
            stream_name=stream_name,
        )

        # Add the CloudWatch handler
        app.logger.addHandler(cloudwatch_handler)
        logging.getLogger("werkzeug").addHandler(cloudwatch_handler)

        # Add StreamHandler for local debugging and instance logs
        app.logger.addHandler(logging.StreamHandler())
        app.logger.setLevel(logging.INFO)
        app.logger.info(f"App startup on instance {instance_id}")

    except (ClientError, NoCredentialsError, Exception) as e:
        # Catch ALL AWS errors so app works locally without creds
        fallback_handler = logging.StreamHandler()
        app.logger.addHandler(fallback_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.warning(f"CloudWatch logging disabled: {e}")



def create_app():
    """Create and configure the Flask application."""
    global limiter
    app = Flask(__name__)

    # Load configuration
    config = get_config()
    app.config.from_object(config)

    # Configure app to work with proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Initialize migrations
    db.init_app(app)

    migrate.init_app(app, db)

    # Initialize Sentry
    if not app.debug:
        sentry_sdk.init(
            dsn=app.config["SENTRY_DSN"],
            integrations=[FlaskIntegration(transaction_style="url")],
            traces_sample_rate=1.0,
            environment=app.config["FLASK_ENV"],
        )

        setup_cloudwatch_logging(app)

        Talisman(
            app,
            content_security_policy={
                "default-src": "'self'",
                "script-src": [
                    "'self'",
                    "'unsafe-inline'",
                    "https://cdnjs.cloudflare.com",
                    "https://code.jquery.com",
                    "https://cdn.jsdelivr.net",
                ],
                "style-src": [
                    "'self'",
                    "'unsafe-inline'",
                    "https://stackpath.bootstrapcdn.com",
                    "https://fonts.googleapis.com",
                    "https://code.jquery.com",
                ],
                "img-src": ["'self'", "data:", "https:"],
                "font-src": ["'self'", "https:", "data:", "https://fonts.gstatic.com"],
                "connect-src": ["'self'", "https://maps.googleapis.com", "https://api.ipify.org"],
            },
            force_https=True,
            strict_transport_security=True,
            session_cookie_secure=True,
            session_cookie_http_only=True,
        )

    # Initialize Redis
    try:
        redis_client = redis.Redis(
            host=app.config["REDIS_HOST"],
            port=app.config["REDIS_PORT"],
            decode_responses=True,
            password=app.config["REDIS_PASSWORD"],
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        redis_client.ping()  # Test connection
        app.config["REDIS_CLIENT"] = redis_client
        
        # Initialize rate limiter with Redis
        redis_uri = f"redis://{app.config['REDIS_HOST']}:{app.config['REDIS_PORT']}"
        if app.config.get('REDIS_PASSWORD'):
            redis_uri = f"redis://:{app.config['REDIS_PASSWORD']}@{app.config['REDIS_HOST']}:{app.config['REDIS_PORT']}"
            
        limiter = Limiter(
            get_remote_address,
            storage_uri=redis_uri,
            storage_options={"socket_connect_timeout": 30},
            strategy="fixed-window-elastic-expiry",
        )
        limiter.init_app(app)
        
    except (redis.ConnectionError, redis.exceptions.ConnectionError):
        app.logger.warning("Failed to connect to Redis, falling back to in-memory storage")
        
        # Mock Redis for local development
        class MockRedis:
            def __init__(self):
                self.store = {}
            def get(self, key):
                return self.store.get(key)
            def setex(self, key, time, value):
                self.store[key] = value
            def set(self, key, value):
                self.store[key] = value
                
        app.config["REDIS_CLIENT"] = MockRedis()
        
        # Initialize rate limiter with memory storage
        limiter = Limiter(
            get_remote_address,
            storage_uri="memory://",
        )
        limiter.init_app(app)
    except Exception as e:
        app.logger.error(f"Failed to initialize services: {str(e)}")
        # Allow app to start even if services fail, but log error
        pass

    # Register blueprints
    from .api_routes import api
    from .frontend_routes import main

    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(main)

    # Create database tables
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"Failed to create database tables: {str(e)}")
            raise

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors."""
        return jsonify({"html": render_template("error.html"), "is_home": False}), 404

    @app.errorhandler(400)
    def bad_request_error(error):
        """Handle 400 errors."""
        return jsonify({"html": render_template("error.html"), "is_home": False}), 400

    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limit errors."""
        return redirect(url_for("main.catch_all"))

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        db.session.rollback()
        app.logger.error("Server Error: %s", str(error))
        return jsonify({"html": render_template("error.html"), "is_home": False}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        """Handle unhandled exceptions."""
        app.logger.error("Unhandled Exception: %s", str(e))
        return jsonify({"html": render_template("error.html"), "is_home": False}), 500

    return app
