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
    # games in progress (with players in them) of the whole platform, every
    # game and service included: Session.models.OccupiedGame
    "MAX_ACTIVE_SESSIONS": 20,
    # an active session nobody has launched for that long is archived
    "SESSION_IDLE_DURATION": 15, # in days
    # an archived session is deleted after that long
    "SESSION_ARCHIVE_DURATION": 180, # in days
}

BAD_REQUEST = "Bad Request"
FORBIDDEN = "Forbidden"
FORBIDDEN_METHOD = "Forbidden method"
CONFLICT = "Conflict"
UNAUTHORIZED = "Unauthorized"
INVALID_NATIONALITY = "Invalid nationality"
PLATFORM_FULL = "Maximum number of active games reached"
