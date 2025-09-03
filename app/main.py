import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import signal
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import create_database, get_session, User
from services.lock_api import LockAPIService
from services.excel import ExcelService
from services.email import EmailService
from services.strike import StrikeService
from config import Config
from utils.logger import setup_logger

class LockMonitorApp:
    def __init__(self, enable_emails=True, enable_cloud_deletion=True):
        self.logger = setup_logger('LockMonitorApp')
        self.config = Config()

        self.enable_emails = enable_emails
        self.enable_cloud_deletion = enable_cloud_deletion

        create_database(self.config.DATABASE_PATH)

        self.lock_api = LockAPIService(self.config)
        self.excel_service = ExcelService(self.config)
        self.email_service = EmailService(self.config)
        self.strike_service = StrikeService(self.config)

        if not enable_emails:
            self.logger.info("⚠️  EMAIL SENDING DISABLED (test mode)")
        if not enable_cloud_deletion:
            self.logger.info("⚠️  CLOUD DELETION DISABLED (test mode)")

        self.logger.info("LockMonitorApp initialized successfully")

    def check_locks_and_process(self):
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
        try:
            card_uid = violation['card_uid']
            self.logger.info(f"Processing violation for card UID: {card_uid}")

            user_info = self.excel_service.get_user_info(card_uid)
            if not user_info:
                self.logger.warning(f"No user info found for card UID: {card_uid}")
                return

            strike_info = self.strike_service.process_strike(card_uid, violation)

            if strike_info.get('strike_type') == 'no_action':
                self.logger.info(f"🔄 No action required for {user_info['name']} ({card_uid}): {strike_info.get('reason', 'No action needed')}")
                return

            if self.enable_emails:
                self.email_service.send_strike_email(user_info, strike_info)
                self.logger.info(f"✅ Email sent for {strike_info['strike_type']} to {user_info['name']}")
            else:
                self.logger.info(f"📧 EMAIL SKIPPED (test mode): Would send {strike_info['strike_type']} email to {user_info['name']}")

            if strike_info['strike_type'] == 'strike_3':
                self._handle_strike_three(card_uid, user_info)

        except Exception as e:
            self.logger.error(f"Error processing violation for {violation['card_uid']}: {str(e)}")

    def _handle_strike_three(self, card_uid, user_info):
        try:
            if self.enable_cloud_deletion:
                success = self.lock_api.delete_card_from_cloud(card_uid)
                if success:
                    self.logger.info(f"✅ Successfully deleted card {card_uid} from cloud")
                else:
                    self.logger.error(f"❌ Failed to delete card {card_uid} from cloud")

                self.excel_service.delete_user(card_uid)
                self.logger.info(f"✅ Deleted user {card_uid} from Excel database")
            else:
                self.logger.info(f"🚫 DELETION SKIPPED (test mode): Would delete card {card_uid} from cloud and Excel")

        except Exception as e:
            self.logger.error(f"Error handling strike 3 for {card_uid}: {str(e)}")

    def _cleanup_old_strikes(self):
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.STRIKE_CLEANUP_DAYS)

            session = get_session(self.config.DATABASE_PATH)
            try:
                users_to_clean = session.query(User).filter(
                    (User.strike_1_date < cutoff_date) |
                    (User.strike_2_date < cutoff_date)
                ).all()

                cleaned_count = 0
                for user in users_to_clean:
                    strike_1_date = user.strike_1_date
                    strike_2_date = user.strike_2_date

                    if strike_1_date and strike_1_date.tzinfo is None:
                        strike_1_date = strike_1_date.replace(tzinfo=timezone.utc)
                    if strike_2_date and strike_2_date.tzinfo is None:
                        strike_2_date = strike_2_date.replace(tzinfo=timezone.utc)

                    newest_strike_date = None
                    if strike_1_date and strike_2_date:
                        newest_strike_date = max(strike_1_date, strike_2_date)
                    elif strike_1_date:
                        newest_strike_date = strike_1_date
                    elif strike_2_date:
                        newest_strike_date = strike_2_date

                    if newest_strike_date and newest_strike_date < cutoff_date:
                        user.strike_1_date = None  # type: ignore[assignment]
                        user.strike_2_date = None  # type: ignore[assignment]
                        user.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                        cleaned_count += 1

                session.commit()
                self.logger.info(f"Cleaned up old strikes for {cleaned_count} users")

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error during strike cleanup: {str(e)}")

    def run_scheduler(self):
        scheduler = BlockingScheduler()

        scheduler.add_job(
            func=self.check_locks_and_process,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_lock_check',
            name='Daily Lock Status Check',
            replace_existing=True
        )

        scheduler.add_job(
            func=self._cleanup_old_strikes,
            trigger=CronTrigger(day_of_week=0, hour=1, minute=0),
            id='weekly_cleanup',
            name='Weekly Strike Cleanup',
            replace_existing=True
        )

        self.logger.info("Scheduler started. Waiting for scheduled jobs...")
        self.logger.info("Next run: Tomorrow at 00:00")

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

    def run_once(self, enable_emails=True, enable_cloud_deletion=True):
        self.enable_emails = enable_emails
        self.enable_cloud_deletion = enable_cloud_deletion

        self.logger.info("Running lock check process once...")
        if not enable_emails:
            self.logger.info("⚠️  Emails disabled for this run")
        if not enable_cloud_deletion:
            self.logger.info("⚠️  Cloud deletion disabled for this run")

        self.check_locks_and_process()

def main():
    parser = argparse.ArgumentParser(description='Lock Monitor Application')
    parser.add_argument('--once', action='store_true', help='Run once instead of scheduler')
    parser.add_argument('--no-emails', action='store_true', help='Skip sending emails (for testing)')
    parser.add_argument('--no-cloud-deletion', action='store_true', help='Skip cloud deletion (for testing)')
    parser.add_argument('--test-mode', action='store_true', help='Enable full test mode (no emails, no deletion)')

    args = parser.parse_args()

    enable_emails = not (args.no_emails or args.test_mode)
    enable_cloud_deletion = not (args.no_cloud_deletion or args.test_mode)

    app = LockMonitorApp(enable_emails=enable_emails, enable_cloud_deletion=enable_cloud_deletion)

    if args.once:
        app.run_once(enable_emails=enable_emails, enable_cloud_deletion=enable_cloud_deletion)
    else:
        app.run_scheduler()

if __name__ == "__main__":
    main()
