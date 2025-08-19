import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logger(name: str, config=None):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    if config:
        log_level = getattr(config, 'LOG_LEVEL', 'INFO')
        log_file = getattr(config, 'LOG_FILE', 'logs/lock_monitor.log')
        max_bytes = getattr(config, 'LOG_MAX_BYTES', 10485760)  # 10MB
        backup_count = getattr(config, 'LOG_BACKUP_COUNT', 5)
    else:
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        log_file = os.getenv('LOG_FILE', 'logs/lock_monitor.log')
        max_bytes = int(os.getenv('LOG_MAX_BYTES', '10485760'))
        backup_count = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    logger.setLevel(getattr(logging, log_level.upper()))

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

def get_logger(name: str):
    """
    Get existing logger or create new one with basic configuration

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def log_application_start(logger, config=None):
    logger.info("=" * 60)
    logger.info("LOCK MONITOR APPLICATION STARTING")
    logger.info("=" * 60)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if config:
        logger.info(f"Database: {getattr(config, 'DATABASE_PATH', 'N/A')}")
        logger.info(f"Excel DB: {getattr(config, 'EXCEL_USER_DATABASE', 'N/A')}")
        logger.info(f"Monitored Units: {getattr(config, 'MONITORED_UNITS', 'N/A')}")
        logger.info(f"Test Mode: {getattr(config, 'TEST_MODE', 'N/A')}")

    logger.info("=" * 60)

def log_application_stop(logger):
    logger.info("=" * 60)
    logger.info("LOCK MONITOR APPLICATION STOPPING")
    logger.info(f"Stop time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
