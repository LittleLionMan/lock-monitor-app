import requests
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

class LockAPIService:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        self.base_url = "https://smartlocks.burgcloud.com/burg/rest"

        self.login_url = f"{self.base_url}/m2mgate/authentication/login"
        self.device_url = f"{self.base_url}/device/lock"

        # Authentication
        self.token = None
        self.token_expires_at = None

    def authenticate(self) -> bool:
        """Authenticate and get access token"""
        try:
            payload = {
                "email": self.config.BURG_EMAIL,
                "password": self.config.BURG_PASSWORD
            }

            headers = {
                "accept": "application/json",
                "Content-Type": "application/json"
            }

            params = {
                "fetch-user-data": "false",
                "ui-permissions-only": "true"
            }

            self.logger.info("Authenticating with Burg Cloud API...")

            response = requests.post(
                self.login_url,
                json=payload,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")

                if self.token:
                    self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                    self.logger.info("Authentication successful")
                    return True
                else:
                    self.logger.error("No token in response")
                    return False
            else:
                self.logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Authentication request failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False

    def _is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.token or not self.token_expires_at:
            return False
        return datetime.now(timezone.utc) < (self.token_expires_at - timedelta(minutes=5))

    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid token"""
        if self._is_token_valid():
            return True

        return self.authenticate()

    def get_lock_status(self, locations: List[str]) -> Optional[Dict]:
        if not self._ensure_authenticated():
            self.logger.error("Failed to authenticate")
            return None

        all_lock_data = {}

        for location in locations:
            try:
                self.logger.info(f"Fetching lock status for location: {location}")

                headers = {
                    "accept": "application/json",
                    "Authorization": f"Bearer {self.token}"
                }

                params = {
                    "orga-unit-id": location
                }

                response = requests.get(
                    self.device_url,
                    headers=headers,
                    params=params,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    locks = self._parse_lock_data(data)
                    all_lock_data[location] = locks
                    self.logger.info(f"Retrieved {len(locks)} locks for location {location}")

                elif response.status_code == 401:
                    self.logger.warning("Token expired, re-authenticating...")
                    if self.authenticate() and self.token:
                        headers["X-Auth-Token"] = self.token
                        response = requests.get(self.device_url, headers=headers, params=params, timeout=30)
                        if response.status_code == 200:
                            data = response.json()
                            locks = self._parse_lock_data(data)
                            all_lock_data[location] = locks
                        else:
                            self.logger.error(f"Failed to get locks for {location} after re-auth: {response.status_code}")
                    else:
                        self.logger.error("Re-authentication failed")

                else:
                    self.logger.error(f"Failed to get locks for {location}: {response.status_code} - {response.text}")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed for location {location}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error getting locks for {location}: {str(e)}")

        return all_lock_data if all_lock_data else None

    def _parse_lock_data(self, api_data) -> List[Dict]:
        locks = []

        try:
            devices = api_data if isinstance(api_data, list) else [api_data]

            for device in devices:
                lock_info = {
                    "lock_id": str(device.get("id", "unknown")),
                    "is_locked": device.get("locked", False),
                    "locked_by_uid": device.get("lastUsedRfid"),
                    "locked_at": device.get("lastOpenCloseDate")
                }

                if lock_info["locked_at"]:
                    try:
                        datetime.fromisoformat(lock_info["locked_at"].replace('Z', '+00:00'))
                    except ValueError:
                        self.logger.warning(f"Invalid timestamp format: {lock_info['locked_at']}")
                        lock_info["locked_at"] = None

                locks.append(lock_info)

        except Exception as e:
            self.logger.error(f"Error parsing Burg lock data: {str(e)}")
            self.logger.debug(f"Raw API data: {api_data}")

        return locks

    def delete_card_from_cloud(self, card_uid: str) -> bool:
        if not self._ensure_authenticated():
            self.logger.error("Failed to authenticate for card deletion")
            return False

        try:
            self.logger.info(f"Starting deletion process for card {card_uid}...")

            success_count = 0
            location_ids = self.config.WHITELIST_LOCATIONS

            for location_id in location_ids:
                try:
                    removed = self._remove_card_from_location_lists(card_uid, location_id)
                    if removed:
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"Error processing location {location_id}: {str(e)}")

            if success_count > 0:
                self.logger.info(f"Successfully processed card {card_uid} deletion in {success_count}/{len(location_ids)} locations")
                return True
            else:
                self.logger.info(f"Card {card_uid} was not found in any RFID lists")
                return True

        except Exception as e:
            self.logger.error(f"Error during card deletion process for {card_uid}: {str(e)}")
            return False

    def _remove_card_from_location_lists(self, card_uid: str, location_id: str) -> bool:
        try:
            rfid_lists = self._get_location_rfid_lists(location_id)
            if not rfid_lists:
                return False

            removal_success = False

            for rfid_list in rfid_lists:
                list_id = rfid_list.get('id')
                rfid_string = rfid_list.get('rfidList', '')

                if not list_id or not rfid_string:
                    continue

                if card_uid in rfid_string:
                    updated_rfid_string = self._remove_uid_from_string(rfid_string, card_uid)

                    success = self._update_rfid_list(location_id, list_id, rfid_list['name'], updated_rfid_string)
                    if success:
                        self.logger.info(f"Removed card {card_uid} from RFID list {list_id} in location {location_id}")
                        removal_success = True
                    else:
                        self.logger.error(f"Failed to update RFID list {list_id} in location {location_id}")

            return removal_success

        except Exception as e:
            self.logger.error(f"Error removing card from location {location_id}: {str(e)}")
            return False

    def _get_location_rfid_lists(self, location_id: str) -> List[Dict]:
        try:
            headers = {
                "accept": "application/json"
            }

            if self.token:
                headers["X-Auth-Token"] = self.token

            url = f"{self.base_url}/orga-unit/locations/{location_id}/rfid-lists"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            elif response.status_code == 401:
                if self.authenticate() and self.token:
                    headers["X-Auth-Token"] = self.token
                    response = requests.get(url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        return data if isinstance(data, list) else []

            return []

        except Exception as e:
            self.logger.error(f"Error getting RFID lists for location {location_id}: {str(e)}")
            return []

    def _remove_uid_from_string(self, rfid_string: str, card_uid: str) -> str:
        try:
            uid_list = [uid.strip() for uid in rfid_string.split(',') if uid.strip()]
            updated_list = [uid for uid in uid_list if uid != card_uid]
            return ','.join(updated_list)
        except Exception as e:
            self.logger.error(f"Error removing UID from string: {str(e)}")
            return rfid_string

    def _update_rfid_list(self, location_id: str, list_id: str, name: str, rfid_list: str) -> bool:
        try:
            headers = {
                "accept": "*/*",
                "Content-Type": "application/json"
            }

            if self.token:
                headers["X-Auth-Token"] = self.token

            payload = {
                "id": int(location_id),
                "name": name,
                "listType": "WhiteList",
                "rfidList": rfid_list,
                "locationId": 0
            }

            url = f"{self.base_url}/orga-unit/locations/{location_id}/rfid-lists/{list_id}"
            response = requests.put(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                # Re-authenticate and retry
                if self.authenticate() and self.token:
                    headers["X-Auth-Token"] = self.token
                    response = requests.put(url, json=payload, headers=headers, timeout=30)
                    return response.status_code == 200

            self.logger.error(f"Failed to update RFID list: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            self.logger.error(f"Error updating RFID list: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test if API connection works"""
        return self.authenticate()
