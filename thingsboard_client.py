"""
ThingsBoard API Client for fetching CCMS panel telemetry data.
Fetches real customer device inventory and server-scope attributes using concurrent requests.
"""
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from config import Config
from mock_data import get_mock_telemetry_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class ThingsBoardClient:
    def __init__(self):
        self.base_url = Config.THINGSBOARD_URL
        self.username = Config.THINGSBOARD_USERNAME
        self.password = Config.THINGSBOARD_PASSWORD
        self.customer_id = getattr(Config, "BBMP_CUSTOMER_ID", "e2119df0-45c3-11f0-94dc-77130b2f47e9")
        self.token = None

    def login(self) -> bool:
        """
        Authenticates with ThingsBoard and saves the JWT token.
        """
        if not self.username or not self.password:
            logger.warning("ThingsBoard credentials not provided in environment.")
            return False

        login_url = f"{self.base_url}/api/auth/login"
        payload = {"username": self.username, "password": self.password}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            resp = requests.post(login_url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                self.token = resp.json().get("token")
                logger.info("Successfully authenticated with ThingsBoard API.")
                return True
            else:
                logger.warning(f"ThingsBoard login failed: HTTP {resp.status_code} - {resp.text[:200]}")
                return False
        except Exception as e:
            logger.warning(f"ThingsBoard connection error: {e}")
            return False

    def fetch_panels_telemetry(self) -> list:
        """
        Fetches panel devices and their telemetry/attribute status from ThingsBoard.
        Falls back to realistic mock telemetry if API login fails or FORCE_MOCK_DATA is set.
        """
        if Config.FORCE_MOCK_DATA:
            logger.info("FORCE_MOCK_DATA is enabled. Using simulated BBMP telemetry.")
            return get_mock_telemetry_data(Config.OFFLINE_DAYS_THRESHOLD)

        if not self.login():
            logger.warning("Could not authenticate with ThingsBoard. Falling back to simulated BBMP telemetry.")
            return get_mock_telemetry_data(Config.OFFLINE_DAYS_THRESHOLD)

        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"Bearer {self.token}"
        }

        try:
            # 1. Fetch all customer devices with pagination
            all_devices = []
            page = 0
            page_size = 1000
            
            # Determine API URL (Customer deviceInfos or Tenant devices)
            if self.customer_id:
                base_device_url = f"{self.base_url}/api/customer/{self.customer_id}/deviceInfos"
            else:
                base_device_url = f"{self.base_url}/api/tenant/devices"

            logger.info(f"Querying ThingsBoard devices from {base_device_url}...")
            while True:
                url = f"{base_device_url}?pageSize={page_size}&page={page}"
                resp = requests.get(url, headers=headers, timeout=25)
                if resp.status_code != 200:
                    logger.warning(f"Failed to query devices page {page}: HTTP {resp.status_code}")
                    break
                data = resp.json()
                batch = data.get("data", [])
                all_devices.extend(batch)
                if not data.get("hasNext") or len(batch) == 0:
                    break
                page += 1

            if not all_devices:
                logger.warning("No devices retrieved from ThingsBoard. Falling back to mock data.")
                return get_mock_telemetry_data(Config.OFFLINE_DAYS_THRESHOLD)

            logger.info(f"Retrieved {len(all_devices)} live devices from ThingsBoard.")

            now_ms = time.time() * 1000
            session = requests.Session()
            session.headers.update(headers)
            attr_cache = {}

            # 2. High-performance batch attribute querying via /api/entitiesQuery/find
            logger.info(f"Retrieving telemetry & attributes for {len(all_devices)} devices using concurrent batch queries...")
            batch_size = 500
            batches = [all_devices[i:i + batch_size] for i in range(0, len(all_devices), batch_size)]

            def fetch_attr_batch(b):
                ids = [d.get("id", {}).get("id") for d in b if d.get("id", {}).get("id")]
                payload = {
                    "entityFilter": {
                        "type": "entityList",
                        "entityType": "DEVICE",
                        "entityList": ids
                    },
                    "pageLink": {
                        "pageSize": len(ids),
                        "page": 0
                    },
                    "latestValues": [
                        {"type": "TIME_SERIES", "key": "systime"},
                        {"type": "TIME_SERIES", "key": "faultCode"},
                        {"type": "TIME_SERIES", "key": "pkt"},
                        {"type": "TIME_SERIES", "key": "rv"},
                        {"type": "TIME_SERIES", "key": "yv"},
                        {"type": "TIME_SERIES", "key": "bv"},
                        {"type": "SERVER_ATTRIBUTE", "key": "active"},
                        {"type": "SERVER_ATTRIBUTE", "key": "lastActivityTime"},
                        {"type": "SERVER_ATTRIBUTE", "key": "lastConnectTime"},
                        {"type": "SERVER_ATTRIBUTE", "key": "wardName"},
                        {"type": "SERVER_ATTRIBUTE", "key": "zoneName"},
                        {"type": "SERVER_ATTRIBUTE", "key": "region"},
                        {"type": "SERVER_ATTRIBUTE", "key": "location"},
                        {"type": "SHARED_ATTRIBUTE", "key": "wardName"},
                        {"type": "SHARED_ATTRIBUTE", "key": "zoneName"},
                        {"type": "SHARED_ATTRIBUTE", "key": "region"},
                        {"type": "SHARED_ATTRIBUTE", "key": "location"}
                    ]
                }
                out = {}
                try:
                    resp = session.post(f"{self.base_url}/api/entitiesQuery/find", json=payload, timeout=20)
                    if resp.status_code == 200:
                        for item in resp.json().get("data", []):
                            eid = item.get("entityId", {}).get("id")
                            latest = item.get("latest", {})
                            item_attrs = {}
                            for scope in ("SERVER_ATTRIBUTE", "SHARED_ATTRIBUTE", "CLIENT_ATTRIBUTE", "TIME_SERIES"):
                                for k, val_dict in latest.get(scope, {}).items():
                                    item_attrs[k] = val_dict.get("value")
                            out[eid] = item_attrs
                except Exception as ex:
                    logger.warning(f"Batch attribute query warning: {ex}")
                return out

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(fetch_attr_batch, b) for b in batches]
                for f in as_completed(futures):
                    attr_cache.update(f.result())

            logger.info(f"Successfully retrieved telemetry attributes for {len(attr_cache)} devices.")

            # 3. Assemble standardized panel telemetry records
            panels = []
            now_sec = time.time()

            # Load known PF (Power Failure) panel definitions
            import os, json
            pf_file = os.path.join(os.path.dirname(__file__), "pf_panels.json")
            pf_ids, pf_meters, pf_feeders = set(), set(), set()
            if os.path.exists(pf_file):
                try:
                    with open(pf_file, "r", encoding="utf-8") as f:
                        pf_info = json.load(f)
                        pf_ids = set(pf_info.get("device_ids", []))
                        pf_meters = set(pf_info.get("meter_numbers", []))
                        pf_feeders = set(pf_info.get("feeder_names", []))
                except Exception as ex:
                    logger.warning(f"Could not read pf_panels.json: {ex}")

            for device in all_devices:
                dev_id = device.get("id", {}).get("id")
                device_name = device.get("name", "Unknown")
                device_label = device.get("label", device_name)
                groups = device.get("groups", [])

                attrs = attr_cache.get(dev_id, {})
                zone = attrs.get("zoneName") or attrs.get("region")
                ward = attrs.get("wardName") or "BBMP Ward"

                # Check group name if zone not yet resolved
                if not zone and groups:
                    g_name = groups[0].get("name", "").strip()
                    if g_name and "park" not in g_name.lower():
                        zone = g_name

                # Standardize zone names into the two official BBMP regions: EAST Region and Bommanahalli Region
                z_check = (str(zone or "") + " " + str(device_name) + " " + str(device_label)).lower()
                if "bommanahalli" in z_check or "bommanahali" in z_check:
                    zone = "Bommanahalli Region"
                else:
                    zone = "EAST Region"

                # Prioritize systime (the actual electrical packet timestamp displayed in ThingsBoard dashboard)
                systime_val = attrs.get("systime")
                last_ms_val = attrs.get("lastActivityTime") or attrs.get("lastConnectTime")
                raw_active = attrs.get("active")

                if systime_val:
                    try:
                        systime_sec = float(systime_val)
                        diff_sec = max(0, now_sec - systime_sec)
                        diff_hours = diff_sec / 3600.0
                        offline_days = int(diff_sec / 86400.0)
                        last_activity_time = datetime.fromtimestamp(systime_sec)
                        is_active = (diff_hours <= 24)
                    except Exception:
                        offline_days = 7
                        last_activity_time = datetime.now()
                        is_active = False
                elif last_ms_val:
                    try:
                        last_ms_float = float(last_ms_val)
                        diff_ms = max(0, now_ms - last_ms_float)
                        diff_hours = diff_ms / (1000 * 3600)
                        offline_days = int(diff_ms / (1000 * 3600 * 24))
                        last_activity_time = datetime.fromtimestamp(last_ms_float / 1000.0)
                        is_active = (diff_hours <= 24)
                    except Exception:
                        offline_days = 7
                        last_activity_time = datetime.now()
                        is_active = False
                else:
                    is_active = (raw_active in (True, "true", "True") or device.get("active", False))
                    offline_days = 0 if is_active else 7
                    last_activity_time = datetime.now()

                # Power failure (PF) detection
                fault_code_val = str(attrs.get("faultCode") or "").strip()
                pkt_val = str(attrs.get("pkt") or "").strip()
                try:
                    rv_val = float(attrs.get("rv") or 0)
                    yv_val = float(attrs.get("yv") or 0)
                    bv_val = float(attrs.get("bv") or 0)
                except Exception:
                    rv_val, yv_val, bv_val = 0, 0, 0

                is_pf = False
                if dev_id in pf_ids or device_name in pf_meters or device_label in pf_feeders:
                    is_pf = True
                elif pkt_val == "8":
                    is_pf = True

                # Root cause categorization
                if is_active:
                    offline_days = 0
                    root_cause = "Normal Operation"
                elif is_pf:
                    root_cause = "Power Failure / Feeder Outage (PF)"
                else:
                    if offline_days >= 30:
                        root_cause = "Long-Term Inactive / Feeder Disconnected (>30D)"
                    elif offline_days >= 14:
                        root_cause = "Chronic Inactivity / MCB Trip (>14D)"
                    elif offline_days >= 7:
                        root_cause = "Communication Inactive (>7D)"
                    elif offline_days >= 1:
                        root_cause = "Network / Gateway Signal Fluctuation (1-7D)"
                    else:
                        root_cause = "Recent Check-in Lag (<24H)"

                panels.append({
                    "panel_id": device_name,
                    "panel_name": device_label,
                    "zone": zone,
                    "ward": ward,
                    "is_active": is_active,
                    "status": "Online" if is_active else "Offline",
                    "last_activity_time": last_activity_time.strftime("%Y-%m-%d %H:%M"),
                    "offline_days": offline_days,
                    "root_cause_tag": root_cause,
                    "is_pf": is_pf,
                    "customer": Config.TARGET_CUSTOMER
                })

            return panels

        except Exception as e:
            logger.error(f"Error while retrieving ThingsBoard device telemetry: {e}")
            logger.info("Falling back to simulated BBMP telemetry data.")
            return get_mock_telemetry_data(Config.OFFLINE_DAYS_THRESHOLD)
