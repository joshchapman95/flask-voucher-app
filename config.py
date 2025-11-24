import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

load_dotenv()  # Load .env file for development

def get_ssm_parameters(path):
    """Get parameters from AWS SSM Parameter Store."""
    try:
        # Create a boto3 session
        session = boto3.Session(region_name='ap-southeast-2')
        ssm = session.client('ssm')
        
        parameters = {}
        response = ssm.get_parameters_by_path(
            Path=path,
            Recursive=True,
            WithDecryption=True
        )
        for param in response['Parameters']:
            name = param['Name'].split('/')[-1]
            parameters[name] = param['Value']
        return parameters
    except (ClientError, NoCredentialsError, BotoCoreError) as e:
        # In local development without AWS creds, this might fail.
        # We'll log it but return empty dict to fallback to env vars.
        print(f"Warning: Could not fetch parameters from SSM: {e}")
        return {}

# Cache SSM parameters to avoid repeated calls
_ssm_params = None

def get_config_value(key, default=None):
    """Get configuration value from env vars or SSM."""
    # 1. Try Environment Variable first
    val = os.environ.get(key)
    if val is not None:
        return val

    # 2. Try SSM (lazy load)
    global _ssm_params
    if _ssm_params is None:
        # or just try and fail gracefully.
        _ssm_params = get_ssm_parameters('/myapp/')
    
    return _ssm_params.get(key, default)


class Config:
    """Base configuration."""
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = True
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_PASSWORD = get_config_value('REDIS_PASSWORD')
    VOUCHER_DISTANCE = int(os.environ.get('VOUCHER_DISTANCE', 2))
    SQLALCHEMY_DATABASE_URI = get_config_value('DATABASE_URI', 'sqlite:///development.db')
    GOOGLE_PLACES_API_KEY = get_config_value('GOOGLE_PLACES_API_KEY')
    SENTRY_DSN = get_config_value('SENTRY_DSN')

    @classmethod
    def init_app(cls, app):
        """Initialize application configuration."""
        pass

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    @classmethod
    def init_app(cls, app):
        """Initialize application configuration."""
        super().init_app(app)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get the current configuration object."""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])
