import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import signal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import create_database, get_session, User
from services.lock_api import LockAPIService
from services.excel import ExcelService
from services.email import EmailService
from services.strike import StrikeService
from config import Config
from utils.logger import setup_logger

class LockMonitorApp:
    def __init__(self):
        self.logger = setup_logger('LockMonitorApp')
        self.config = Config()

        # Initialize services
        self.lock_api = LockAPIService(self.config)
        self.excel_service = ExcelService(self.config)
        self.email_service = EmailService(self.config)
        self.strike_service = StrikeService(self.config)

        # Initialize database
        create_database(self.config.DATABASE_PATH)

        self.logger.info("LockMonitorApp initialized successfully")

    def check_locks_and_process(self):
        """Main method to check lock status and process violations"""
        try:
            self.logger.info("Starting lock check process...")

            lock_data = self.lock_api.get_lock_status(self.config.MONITORED_UNITS)
            if not lock_data:
                self.logger.error("No lock data received from API")
                return

            violations = self._check_for_violations(lock_data)

            for violation in violations:
                self._process_violation(violation)

            self._cleanup_old_strikes()

            self.logger.info(f"Lock check process completed. Processed {len(violations)} violations.")

        except Exception as e:
            self.logger.error(f"Error during lock check process: {str(e)}", exc_info=True)

    def _check_for_violations(self, lock_data):
        violations = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.config.VIOLATION_HOURS)

        for unit_id, locks in lock_data.items():
            for lock in locks:
                if not lock['is_locked'] or not lock.get('locked_by_uid'):
                    continue

                locked_at_str = lock.get('locked_at')
                if not locked_at_str:
                    continue

                try:
                    if isinstance(locked_at_str, str):
                        if locked_at_str.endswith('Z'):
                            locked_at = datetime.fromisoformat(locked_at_str.replace('Z', '+00:00'))
                        elif '+' in locked_at_str or '-' in locked_at_str[-6:]:
                            locked_at = datetime.fromisoformat(locked_at_str)
                        else:
                            locked_at = datetime.fromisoformat(locked_at_str).replace(tzinfo=timezone.utc)
                    else:
                        locked_at = locked_at_str
                        if locked_at.tzinfo is None:
                            locked_at = locked_at.replace(tzinfo=timezone.utc)
                    if locked_at < cutoff_time:
                        if self.strike_service.is_user_in_cooldown(lock['locked_by_uid']):
                            self.logger.debug(f"User {lock['locked_by_uid']} is in cooldown, skipping")
                            continue

                        violations.append({
                            'location': unit_id,
                            'lock_id': lock['lock_id'],
                            'card_uid': lock['locked_by_uid'],
                            'locked_at': locked_at
                        })

                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not parse timestamp for lock {lock['lock_id']}: {locked_at_str} - {str(e)}")
                    continue

        return violations

    def _process_violation(self, violation):
        """Process a single violation"""
        try:
            card_uid = violation['card_uid']
            self.logger.info(f"Processing violation for card UID: {card_uid}")

            # 1. Get user info from Excel
            user_info = self.excel_service.get_user_info(card_uid)
            if not user_info:
                self.logger.warning(f"No user info found for card UID: {card_uid}")
                return

            # 2. Process strike
            strike_info = self.strike_service.process_strike(card_uid, violation)

            # 3. Send email
            self.email_service.send_strike_email(user_info, strike_info)

            # 4. If it's strike 3, delete UID from cloud and Excel
            if strike_info['strike_type'] == 'strike_3':
                self._handle_strike_three(card_uid, user_info)

        except Exception as e:
            self.logger.error(f"Error processing violation for {violation['card_uid']}: {str(e)}")

    def _handle_strike_three(self, card_uid, user_info):
        """Handle strike 3 - delete UID from cloud and Excel"""
        try:
            # Delete from cloud via API
            success = self.lock_api.delete_card_from_cloud(card_uid)
            if success:
                self.logger.info(f"Successfully deleted card {card_uid} from cloud")
            else:
                self.logger.error(f"Failed to delete card {card_uid} from cloud")

            # Delete from Excel
            self.excel_service.delete_user(card_uid)
            self.logger.info(f"Deleted user {card_uid} from Excel database")

        except Exception as e:
            self.logger.error(f"Error handling strike 3 for {card_uid}: {str(e)}")

    def _cleanup_old_strikes(self):
        """Clean up strikes older than configured interval"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.STRIKE_CLEANUP_DAYS)

            session = get_session(self.config.DATABASE_PATH)
            try:
                # Find users with strikes older than cutoff
                users_to_clean = session.query(User).filter(
                    (User.strike_1_date < cutoff_date) |
                    (User.strike_2_date < cutoff_date)
                ).all()

                for user in users_to_clean:
                    # Reset all strikes for this user
                    user.strike_1_date = None
                    user.strike_2_date = None
                    user.counter = 0
                    user.updated_at = datetime.now(timezone.utc)

                session.commit()
                self.logger.info(f"Cleaned up old strikes for {len(users_to_clean)} users")

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error during strike cleanup: {str(e)}")

    def run_scheduler(self):
        """Run the application with scheduler"""
        scheduler = BlockingScheduler()

        # Add job to run every day at midnight
        scheduler.add_job(
            func=self.check_locks_and_process,
            trigger=CronTrigger(hour=0, minute=0),  # Every day at 00:00
            id='daily_lock_check',
            name='Daily Lock Status Check',
            replace_existing=True
        )

        # Add cleanup job to run weekly
        scheduler.add_job(
            func=self._cleanup_old_strikes,
            trigger=CronTrigger(day_of_week=0, hour=1, minute=0),  # Every Sunday at 01:00
            id='weekly_cleanup',
            name='Weekly Strike Cleanup',
            replace_existing=True
        )

        self.logger.info("Scheduler started. Waiting for scheduled jobs...")
        self.logger.info("Next run: Tomorrow at 00:00")

        # Graceful shutdown handler
        def signal_handler(signum, frame):
            self.logger.info("Received shutdown signal. Stopping scheduler...")
            scheduler.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            scheduler.start()
        except KeyboardInterrupt:
            self.logger.info("Application stopped by user")
            scheduler.shutdown()

    def run_once(self):
        """Run the check process once (for testing)"""
        self.logger.info("Running lock check process once...")
        self.check_locks_and_process()

def main():
    """Main entry point"""
    app = LockMonitorApp()

    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once for testing
        app.run_once()
    else:
        # Run with scheduler
        app.run_scheduler()

if __name__ == "__main__":
    main()
