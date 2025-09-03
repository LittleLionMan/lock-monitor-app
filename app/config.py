import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_required_env(key: str) -> str:
    """Get required environment variable or raise error"""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value

def get_required_int(key: str) -> int:
    """Get required integer environment variable or raise error"""
    value = get_required_env(key)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable '{key}' must be a valid integer, got: {value}")

def get_required_bool(key: str) -> bool:
    """Get required boolean environment variable or raise error"""
    value = get_required_env(key)
    return value.lower() == 'true'

def get_required_list(key: str) -> List[str]:
    """Get required comma-separated list from environment variable"""
    value = get_required_env(key)
    return [item.strip() for item in value.split(',') if item.strip()]

class Config:
    """Configuration class for Lock Monitor Application"""

    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    DATABASE_PATH: str = get_required_env('DATABASE_PATH')

    # =============================================================================
    # CLOUD API CONFIGURATION
    # =============================================================================
    CLOUD_EMAIL: str = get_required_env('CLOUD_EMAIL')
    CLOUD_PASSWORD: str = get_required_env('CLOUD_PASSWORD')
    CLOUD_BASE_URL: str = get_required_env('CLOUD_BASE_URL')

    # =============================================================================
    # MONITORING CONFIGURATION
    # =============================================================================
    MONITORED_UNITS: List[str] = get_required_list('MONITORED_UNITS')
    WHITELIST_LOCATIONS: List[str] = get_required_list('WHITELIST_LOCATIONS')

    # =============================================================================
    # STRIKE SYSTEM CONFIGURATION
    # =============================================================================
    VIOLATION_HOURS: int = get_required_int('VIOLATION_HOURS')
    STRIKE_COOLDOWN_HOURS: int = get_required_int('STRIKE_COOLDOWN_HOURS')
    STRIKE_CLEANUP_DAYS: int = get_required_int('STRIKE_CLEANUP_DAYS')

    # =============================================================================
    # EXCEL DATABASE CONFIGURATION
    # =============================================================================
    EXCEL_USER_DATABASE: str = get_required_env('EXCEL_USER_DATABASE')

    # Excel column mapping
    EXCEL_COLUMNS = {
            'supervisor': get_required_env('EXCEL_COL_SUPERVISOR'),
            'gender': get_required_env('EXCEL_COL_GENDER'),
            'firstname': get_required_env('EXCEL_COL_FIRSTNAME'),
            'lastname': get_required_env('EXCEL_COL_LASTNAME'),
            'card_uid': get_required_env('EXCEL_COL_UID')
        }

    # Excel worksheets to check (comma-separated)
    EXCEL_WORKSHEETS: List[str] = get_required_list('EXCEL_WORKSHEETS')

    # =============================================================================
    # EMAIL CONFIGURATION
    # =============================================================================
    SMTP_SERVER: str = get_required_env('SMTP_SERVER')
    SMTP_PORT: int = get_required_int('SMTP_PORT')
    SMTP_USE_TLS: bool = get_required_bool('SMTP_USE_TLS')

    EMAIL_USERNAME: str = get_required_env('EMAIL_USERNAME')
    EMAIL_PASSWORD: str = get_required_env('EMAIL_PASSWORD')

    # Email sender settings - EMAIL_FROM can fallback to EMAIL_USERNAME
    EMAIL_FROM: str = os.getenv('EMAIL_FROM') or get_required_env('EMAIL_USERNAME')
    EMAIL_FROM_NAME: str = get_required_env('EMAIL_FROM_NAME')

    # Email templates
    EMAIL_TEMPLATES = {
        'strike_1': {
            'subject': get_required_env('EMAIL_SUBJECT_STRIKE1'),
            'template_file': 'email_templates/strike_1.txt'
        },
        'strike_2': {
            'subject': get_required_env('EMAIL_SUBJECT_STRIKE2'),
            'template_file': 'email_templates/strike_2.txt'
        },
        'strike_3': {
            'subject': get_required_env('EMAIL_SUBJECT_STRIKE3'),
            'template_file': 'email_templates/strike_3.txt'
        }
    }

    # =============================================================================
    # LOGGING CONFIGURATION
    # =============================================================================
    LOG_LEVEL: str = get_required_env('LOG_LEVEL').upper()
    LOG_FILE: str = get_required_env('LOG_FILE')
    LOG_MAX_BYTES: int = get_required_int('LOG_MAX_BYTES')
    LOG_BACKUP_COUNT: int = get_required_int('LOG_BACKUP_COUNT')

    # =============================================================================
    # SCHEDULER CONFIGURATION
    # =============================================================================
    DAILY_CHECK_HOUR: int = get_required_int('DAILY_CHECK_HOUR')
    DAILY_CHECK_MINUTE: int = get_required_int('DAILY_CHECK_MINUTE')

    CLEANUP_DAY_OF_WEEK: int = get_required_int('CLEANUP_DAY_OF_WEEK')
    CLEANUP_HOUR: int = get_required_int('CLEANUP_HOUR')
    CLEANUP_MINUTE: int = get_required_int('CLEANUP_MINUTE')

    # =============================================================================
    # DEVELOPMENT/TESTING CONFIGURATION
    # =============================================================================
    TEST_MODE: bool = get_required_bool('TEST_MODE')
    TEST_EMAIL_RECIPIENT: str = get_required_env('TEST_EMAIL_RECIPIENT')
    DEBUG: bool = get_required_bool('DEBUG')

    @classmethod
    def validate_config(cls) -> bool:
        """Validate required configuration values"""
        required_fields = [
            ('CLOUD_EMAIL', 'Cloud email address'),
            ('CLOUD_PASSWORD', 'Cloud password'),
            ('CLOUD_BASE_URL', 'Cloud API base URL'),
            ('EMAIL_USERNAME', 'Email username/address'),
            ('EMAIL_PASSWORD', 'Email password/app password'),
            ('SMTP_SERVER', 'SMTP server address'),
            ('SMTP_PORT', 'SMTP port (must be > 0)'),
            ('EXCEL_USER_DATABASE', 'Excel database file path'),
            ('LOG_FILE', 'Log file path'),
            ('VIOLATION_HOURS', 'Violation hours (must be > 0)'),
            ('STRIKE_COOLDOWN_HOURS', 'Strike cooldown hours (must be > 0)'),
            ('STRIKE_CLEANUP_DAYS', 'Strike cleanup days (must be > 0)')
        ]

        missing_fields = []
        invalid_fields = []

        for field, description in required_fields:
            value = getattr(cls, field)
            if not value or (isinstance(value, int) and value <= 0 and field != 'DAILY_CHECK_HOUR' and field != 'DAILY_CHECK_MINUTE'):
                missing_fields.append(f"{field} ({description})")

        # Check lists
        if not cls.MONITORED_UNITS:
            missing_fields.append("MONITORED_UNITS (at least one unit to monitor)")

        if not cls.WHITELIST_LOCATIONS:
            missing_fields.append("WHITELIST_LOCATIONS (at least one location for whitelists)")

        if missing_fields:
            print("❌ ERROR: Missing or invalid required configuration:")
            for field in missing_fields:
                print(f"   - {field}")
            print(f"\nPlease check your .env file and ensure these values are set.")
            print(f"See .env.example for the required format.")
            return False

        return True

    @classmethod
    def print_config_summary(cls):
        """Print configuration summary (without sensitive data)"""
        print("=" * 60)
        print("LOCK MONITOR APPLICATION - CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Database Path: {cls.DATABASE_PATH}")
        print(f"Excel Database: {cls.EXCEL_USER_DATABASE}")
        print(f"Monitored Units: {cls.MONITORED_UNITS}")
        print(f"Whitelist Locations: {cls.WHITELIST_LOCATIONS}")
        print(f"Violation Threshold: {cls.VIOLATION_HOURS} hours")
        print(f"Strike Cooldown: {cls.STRIKE_COOLDOWN_HOURS} hours")
        print(f"Strike Cleanup: {cls.STRIKE_CLEANUP_DAYS} days")
        print(f"Daily Check Time: {cls.DAILY_CHECK_HOUR:02d}:{cls.DAILY_CHECK_MINUTE:02d}")
        print(f"SMTP Server: {cls.SMTP_SERVER}:{cls.SMTP_PORT} (TLS: {cls.SMTP_USE_TLS})")
        print(f"Email From: {cls.EMAIL_FROM_NAME} <{cls.EMAIL_FROM}>")
        print(f"Test Mode: {cls.TEST_MODE}")
        print(f"Debug Mode: {cls.DEBUG}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print("=" * 60)

# Create a default instance
config = Config()

if __name__ == "__main__":
    # When run directly, validate and print config
    if Config.validate_config():
        Config.print_config_summary()
        print("✅ Configuration is valid!")
    else:
        print("❌ Configuration validation failed!")
        exit(1)
