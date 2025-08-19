import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from models.database import get_session, User

class StrikeService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_strike(self, card_uid: str, violation: Dict) -> Dict:
        try:
            self.logger.info(f"Processing strike for card UID: {card_uid}")

            session = get_session(self.config.DATABASE_PATH)
            try:
                user = self._get_or_create_user(session, card_uid)

                strike_info = self._determine_and_apply_strike(session, user, violation)

                user.last_violation_date = datetime.now(timezone.utc)
                user.updated_at = datetime.now(timezone.utc)

                session.commit()

                self.logger.info(f"Strike processed: {strike_info['strike_type']} for {card_uid}")
                return strike_info

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error processing strike for {card_uid}: {str(e)}")
            raise e

    def _get_or_create_user(self, session, card_uid: str) -> User:
        try:
            # Try to find existing user
            user = session.query(User).filter(User.card_uid == card_uid).first()

            if user:
                self.logger.debug(f"Found existing user: {card_uid}")
                return user

            self.logger.info(f"Creating new user record for: {card_uid}")
            user = User(
                card_uid=card_uid,
                strike_1_date=None,
                strike_2_date=None,
                counter=0,
                last_violation_date=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            session.add(user)
            return user

        except Exception as e:
            self.logger.error(f"Error getting/creating user {card_uid}: {str(e)}")
            raise e

    def _determine_and_apply_strike(self, session, user: User, violation: Dict) -> Dict:
        try:
            current_time = datetime.now(timezone.utc)

            # Check current strike status
            has_strike_1 = user.strike_1_date is not None
            has_strike_2 = user.strike_2_date is not None
            current_counter = user.counter or 0

            self.logger.debug(f"User {user.card_uid} status: Strike1={has_strike_1}, Strike2={has_strike_2}, Counter={current_counter}")

            # Prepare base strike info
            strike_info = {
                'violation_date': current_time.isoformat(),
                'location': violation.get('location', 'Unknown'),
                'lock_id': violation.get('lock_id', 'Unknown'),
                'counter': current_counter
            }

            # Determine strike type based on current status
            if not has_strike_1:
                # First strike
                user.strike_1_date = current_time
                strike_info['strike_type'] = 'strike_1'
                self.logger.info(f"Applied Strike 1 to user {user.card_uid}")

            elif not has_strike_2:
                # Second strike
                user.strike_2_date = current_time
                strike_info['strike_type'] = 'strike_2'
                self.logger.info(f"Applied Strike 2 to user {user.card_uid}")

            else:
                # Third strike or higher - delete strikes and increment counter
                user.strike_1_date = None
                user.strike_2_date = None
                user.counter = current_counter + 1
                strike_info['strike_type'] = 'strike_3' if current_counter == 0 else 'counter'
                strike_info['counter'] = user.counter
                self.logger.info(f"Applied Strike 3+ (Counter={user.counter}) to user {user.card_uid}")

            return strike_info

        except Exception as e:
            self.logger.error(f"Error determining strike for user {user.card_uid}: {str(e)}")
            raise e

    def get_user_strike_status(self, card_uid: str) -> Optional[Dict]:
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                user = session.query(User).filter(User.card_uid == card_uid).first()

                if not user:
                    return None

                return {
                    'card_uid': user.card_uid,
                    'strike_1_date': user.strike_1_date.isoformat() if user.strike_1_date else None,
                    'strike_2_date': user.strike_2_date.isoformat() if user.strike_2_date else None,
                    'counter': user.counter or 0,
                    'last_violation_date': user.last_violation_date.isoformat() if user.last_violation_date else None,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'updated_at': user.updated_at.isoformat() if user.updated_at else None
                }

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error getting strike status for {card_uid}: {str(e)}")
            return None

    def is_user_in_cooldown(self, card_uid: str) -> bool:
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                user = session.query(User).filter(User.card_uid == card_uid).first()

                if not user or not user.last_violation_date:
                    return False

                # Calculate cooldown cutoff time
                cooldown_cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.STRIKE_COOLDOWN_HOURS)

                # Check if last violation was within cooldown period
                in_cooldown = user.last_violation_date >= cooldown_cutoff

                if in_cooldown:
                    self.logger.debug(f"User {card_uid} is in cooldown period")

                return in_cooldown

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error checking cooldown for {card_uid}: {str(e)}")
            return False

    def reset_user_strikes(self, card_uid: str) -> bool:
        try:
            self.logger.info(f"Resetting strikes for user: {card_uid}")

            session = get_session(self.config.DATABASE_PATH)
            try:
                user = session.query(User).filter(User.card_uid == card_uid).first()

                if not user:
                    self.logger.warning(f"User not found for reset: {card_uid}")
                    return False

                # Reset all strikes
                user.strike_1_date = None
                user.strike_2_date = None
                user.updated_at = datetime.now(timezone.utc)

                session.commit()

                self.logger.info(f"Successfully reset strikes for user: {card_uid}")
                return True

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error resetting strikes for {card_uid}: {str(e)}")
            return False

    def get_all_users_with_strikes(self) -> list:
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                # Query users with any strikes or counters
                users = session.query(User).filter(
                    (User.strike_1_date.isnot(None)) |
                    (User.strike_2_date.isnot(None)) |
                    (User.counter > 0)
                ).all()

                result = []
                for user in users:
                    status = {
                        'card_uid': user.card_uid,
                        'strike_1_date': user.strike_1_date.isoformat() if user.strike_1_date else None,
                        'strike_2_date': user.strike_2_date.isoformat() if user.strike_2_date else None,
                        'counter': user.counter or 0,
                        'last_violation_date': user.last_violation_date.isoformat() if user.last_violation_date else None,
                        'created_at': user.created_at.isoformat() if user.created_at else None,
                        'updated_at': user.updated_at.isoformat() if user.updated_at else None
                    }
                    result.append(status)

                self.logger.info(f"Found {len(result)} users with strikes")
                return result

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error getting users with strikes: {str(e)}")
            return []

    def cleanup_old_strikes(self) -> int:
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.STRIKE_CLEANUP_DAYS)

            self.logger.info(f"Cleaning up strikes where newest strike is older than {cutoff_date}")

            session = get_session(self.config.DATABASE_PATH)
            try:
                # Find users with any strikes
                users_with_strikes = session.query(User).filter(
                    (User.strike_1_date.isnot(None)) |
                    (User.strike_2_date.isnot(None))
                ).all()

                cleaned_count = 0
                for user in users_with_strikes:
                    # Determine the newest (youngest) strike date
                    newest_strike_date = None

                    if user.strike_1_date and user.strike_2_date:
                        # Both strikes exist - take the newer one
                        newest_strike_date = max(user.strike_1_date, user.strike_2_date)
                    elif user.strike_1_date:
                        # Only strike 1 exists
                        newest_strike_date = user.strike_1_date

                    # Clean up only if the newest strike is older than cutoff
                    if newest_strike_date and newest_strike_date < cutoff_date:
                        self.logger.info(f"Cleaning up old strikes for user: {user.card_uid} (newest strike: {newest_strike_date})")
                        user.strike_1_date = None
                        user.strike_2_date = None
                        user.updated_at = datetime.now(timezone.utc)
                        cleaned_count += 1
                    else:
                        self.logger.debug(f"User {user.card_uid} has recent strikes (newest: {newest_strike_date}), skipping cleanup")

                session.commit()

                self.logger.info(f"Cleaned up old strikes for {cleaned_count} users")
                return cleaned_count

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error during strike cleanup: {str(e)}")
            return 0

    def get_strike_statistics(self) -> Dict:
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                # Count users by strike status
                total_users = session.query(User).count()

                users_with_strike_1 = session.query(User).filter(
                    User.strike_1_date.isnot(None)
                ).count()

                users_with_strike_2 = session.query(User).filter(
                    User.strike_2_date.isnot(None)
                ).count()

                users_with_counter = session.query(User).filter(
                    User.counter > 0
                ).count()

                # Get highest counter
                max_counter_user = session.query(User).filter(
                    User.counter > 0
                ).order_by(User.counter.desc()).first()

                max_counter = max_counter_user.counter if max_counter_user else 0

                # Recent violations (last 7 days)
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                recent_violations = session.query(User).filter(
                    User.last_violation_date >= week_ago
                ).count()

                statistics = {
                    'total_users': total_users,
                    'users_with_strike_1': users_with_strike_1,
                    'users_with_strike_2': users_with_strike_2,
                    'users_with_counter': users_with_counter,
                    'highest_counter': max_counter,
                    'recent_violations_7_days': recent_violations,
                    'users_with_any_strikes': users_with_strike_1 + users_with_strike_2 + users_with_counter
                }

                self.logger.info(f"Strike statistics: {statistics}")
                return statistics

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error getting strike statistics: {str(e)}")
            return {}

    def validate_strike_data(self, card_uid: str) -> bool:
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                user = session.query(User).filter(User.card_uid == card_uid).first()

                if not user:
                    return True  # No user = no inconsistency

                # Validation rules:
                # 1. If strike_2_date exists, strike_1_date should also exist (or both be None if counter > 0)
                # 2. strike_1_date should be <= strike_2_date if both exist
                # 3. Counter should be >= 0

                has_strike_1 = user.strike_1_date is not None
                has_strike_2 = user.strike_2_date is not None
                counter = user.counter or 0

                # Rule 1: Strike 2 without Strike 1 (when counter = 0)
                if has_strike_2 and not has_strike_1 and counter == 0:
                    self.logger.warning(f"User {card_uid}: Strike 2 exists without Strike 1")
                    return False

                # Rule 2: Strike dates order
                if has_strike_1 and has_strike_2:
                    if user.strike_1_date > user.strike_2_date:
                        self.logger.warning(f"User {card_uid}: Strike 1 date is after Strike 2 date")
                        return False

                # Rule 3: Counter validation
                if counter < 0:
                    self.logger.warning(f"User {card_uid}: Negative counter value")
                    return False

                return True

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Error validating strike data for {card_uid}: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test database connection for strike service"""
        try:
            session = get_session(self.config.DATABASE_PATH)
            try:
                # Simple query to test connection
                user_count = session.query(User).count()
                self.logger.info(f"Strike service connection test successful. Found {user_count} users.")
                return True
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Strike service connection test failed: {str(e)}")
            return False
