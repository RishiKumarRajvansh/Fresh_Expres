import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,testserver').split(',')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'crispy_forms',
    'crispy_bootstrap4',
    'django_extensions',
    'channels',
]

LOCAL_APPS = [
    'core',
    'accounts',
    'stores',
    'catalog',
    'orders',
    'delivery',
    'locations',
    'chat',
    'payments',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'core.csrf_middleware.CustomCSRFMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.UserTypeAccessMiddleware',  # Add user type access control
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ZipCodeMiddleware',
]

ROOT_URLCONF = 'meat_seafood.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.global_context',
                'core.context_processors.admin_context',
                'core.banner_context.promotional_banners',
            ],
        },
    },
]

WSGI_APPLICATION = 'meat_seafood.wsgi.application'
ASGI_APPLICATION = 'meat_seafood.asgi.application'

# Database
if config('DATABASE_URL', default='').startswith('postgresql'):
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(config('DATABASE_URL'))
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# Redis Configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# Cache Configuration - Use in-memory cache for development
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,
        'MAX_ENTRIES': 1000,
    }
}

# Only use Redis cache in production when explicitly configured
if not DEBUG and config('USE_REDIS', default=False, cast=bool):
    try:
        import redis
        # Test Redis connection
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()  # This will raise an exception if Redis is not available
        
        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': REDIS_URL,
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                }
            }
        }
    except (ImportError, redis.ConnectionError, redis.TimeoutError):
        # Fallback to database cache if Redis is not available
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
                'LOCATION': 'cache_table',
            }
        }

# Session Configuration - Always use database sessions for reliability
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 1 day
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = False

# Channels Configuration - Always use in-memory for development
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    },
}

# Only use Redis channels in production when explicitly configured
if not DEBUG and config('USE_REDIS', default=False, cast=bool):
    try:
        import redis
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()
        
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [REDIS_URL],
                },
            },
        }
    except (ImportError, redis.ConnectionError, redis.TimeoutError):
        # Keep in-memory as fallback
        pass

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@freshmeatseafood.com')
ADMINS = [('Admin', 'ritvik.raj.test1@gmail.com')]

# SMS Configuration
SMS_PROVIDER_API_KEY = config('SMS_PROVIDER_API_KEY', default='')
SMS_PROVIDER_URL = config('SMS_PROVIDER_URL', default='')

# Google Maps API
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='')

# Base URL for callbacks and webhooks
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Payment Gateway Configuration
# PhonePe Configuration
PHONEPE_MERCHANT_ID = config('PHONEPE_MERCHANT_ID', default='')
PHONEPE_SALT_KEY = config('PHONEPE_SALT_KEY', default='')
PHONEPE_SALT_INDEX = config('PHONEPE_SALT_INDEX', default=1, cast=int)
PHONEPE_ENV = config('PHONEPE_ENV', default='SANDBOX')  # SANDBOX or PRODUCTION
PHONEPE_BASE_URL = config('PHONEPE_BASE_URL', default='https://api-preprod.phonepe.com/apis/pg-sandbox')

# Other Payment Gateways (Commented out for future use)
# RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
# RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')

# STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
# STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')

# PAYTM_MERCHANT_ID = config('PAYTM_MERCHANT_ID', default='')
# PAYTM_MERCHANT_KEY = config('PAYTM_MERCHANT_KEY', default='')
# PAYTM_ENVIRONMENT = config('PAYTM_ENVIRONMENT', default='STAGING')

# PAYU_MERCHANT_KEY = config('PAYU_MERCHANT_KEY', default='')
# PAYU_MERCHANT_SALT = config('PAYU_MERCHANT_SALT', default='')
# PAYU_ENV = config('PAYU_ENV', default='test')

# CASHFREE_APP_ID = config('CASHFREE_APP_ID', default='')
# CASHFREE_SECRET_KEY = config('CASHFREE_SECRET_KEY', default='')
# CASHFREE_ENV = config('CASHFREE_ENV', default='TEST')

# Legacy Payment Gateway (Keep for backward compatibility)
PAYMENT_GATEWAY_KEY = config('PAYMENT_GATEWAY_KEY', default='')
PAYMENT_GATEWAY_SECRET = config('PAYMENT_GATEWAY_SECRET', default='')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# Login/Logout URLs
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Twilio Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_VERIFY_SERVICE_SID = config('TWILIO_VERIFY_SERVICE_SID', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')

# OTP Configuration
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5
