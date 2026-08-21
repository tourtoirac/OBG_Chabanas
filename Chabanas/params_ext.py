import os

PARAMS_EXT = {
    "DEBUG": True,
    "SECRET_KEY": 'SECRET_KEY',
    "ALLOWED_HOSTS": [
        "*",
    ],  # list of allowed hosts,
    "CORS_ALLOWED_ORIGINS": [],  # list of allowed CORS Origins
    "CORS_ALLOWED_ORIGIN_REGEXES": [],
    "CSRF_TRUSTED_ORIGINS": [],
    "DATABASES": {
        "default": {
            "ENGINE": 'django.db.backends.postgresql_psycopg2',
            "NAME": 'chabanas',
            "USER": 'django',
            "PASSWORD": os.getenv('DB_PASSWORD', 'a123456789&'),
            "HOST": os.getenv('DB_HOST', 'localhost'),
            "PORT": os.getenv('DB_PORT', "12432"),
            "OPTIONS": {
                "application_name": 'chabanas'
            }
        }
    },
    "MAX_ACTIVE_SESSIONS": 10
}

BAD_REQUEST = "Bad Request"
FORBIDDEN_METHOD = "Forbidden method"
CONFLICT = "Conflict"
UNAUTHORIZED = "Unauthorized"
