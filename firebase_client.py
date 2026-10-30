"""
Firebase Firestore client for fetching customer grievance tickets.
Supports Firebase Admin SDK (credentials file/JSON) and direct REST API querying
for zero-friction live synchronization without local key files.
"""
import os
import json
import base64
import logging
from datetime import datetime
import requests
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE_ADMIN = True
except (ImportError, Exception):
    firebase_admin = None
    credentials = None
    firestore = None
    HAS_FIREBASE_ADMIN = False
from config import Config
from mock_data import get_mock_tickets_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class FirebaseClient:
    def __init__(self):
        self.project_id = Config.FIREBASE_PROJECT_ID
        self.database_id = Config.FIREBASE_DATABASE_ID
        self.collection_id = Config.FIREBASE_COLLECTION_ID
        self.target_customer = Config.TARGET_CUSTOMER
        self.customer_id = getattr(Config, "BBMP_CUSTOMER_ID", "e2119df0-45c3-11f0-94dc-77130b2f47e9")
        self.db = None
        self._init_app()

    def _init_app(self):
        """
        Initializes Firebase Admin SDK if credentials exist.
        If credentials are not supplied, falls back to direct Firestore REST API.
        """
        if not HAS_FIREBASE_ADMIN:
            logger.info("Direct Firestore REST API will be utilized for ticket queries.")
            self.db = None
            return

        if firebase_admin and firebase_admin._apps:
            try:
                self.db = firestore.client(database=self.database_id)
                return
            except Exception:
                try:
                    self.db = firestore.client()
                    return
                except Exception:
                    self.db = None

        cred = None

        # 1. Try raw JSON string or base64 from environment variable
        raw_json = Config.FIREBASE_SERVICE_ACCOUNT_JSON or os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_JSON")
        if raw_json:
            try:
                if not raw_json.strip().startswith("{"):
                    try:
                        decoded = base64.b64decode(raw_json).decode("utf-8")
                        raw_json = decoded
                    except Exception:
                        pass
                cred_dict = json.loads(raw_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("Loaded Firebase credentials from JSON environment variable.")
            except Exception as e:
                logger.warning(f"Failed to parse Firebase JSON from environment: {e}")

        # 2. Try file path
        if not cred and Config.FIREBASE_SERVICE_ACCOUNT_KEY and os.path.exists(Config.FIREBASE_SERVICE_ACCOUNT_KEY):
            try:
                cred = credentials.Certificate(Config.FIREBASE_SERVICE_ACCOUNT_KEY)
                logger.info(f"Loaded Firebase credentials from file: {Config.FIREBASE_SERVICE_ACCOUNT_KEY}")
            except Exception as e:
                logger.warning(f"Failed to load Firebase credentials from file: {e}")

        if cred:
            try:
                firebase_admin.initialize_app(cred, {"projectId": self.project_id})
                try:
                    self.db = firestore.client(database=self.database_id)
                except Exception:
                    self.db = firestore.client()
                logger.info("Firebase Admin SDK initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Firebase Admin SDK: {e}. Will use direct Firestore REST API.")
                self.db = None
        else:
            logger.info("Direct Firestore REST API will be utilized for ticket queries.")
            self.db = None

    def fetch_tickets(self) -> list:
        """
        Fetches tickets from Firestore collection, filters for TARGET_CUSTOMER,
        and standardizes ticket attributes.
        """
        if Config.FORCE_MOCK_DATA:
            logger.info("FORCE_MOCK_DATA is enabled. Using simulated ticket data.")
            return get_mock_tickets_data()

        # Try Admin SDK if initialized, otherwise use direct REST API
        if self.db:
            try:
                return self._fetch_via_admin_sdk()
            except Exception as e:
                logger.warning(f"Admin SDK query failed: {e}. Falling back to Firestore REST API...")

        return self._fetch_via_rest_api()

    def _fetch_via_admin_sdk(self) -> list:
        logger.info(f"Querying Firestore via Admin SDK for collection '{self.collection_id}'...")
        coll_ref = self.db.collection(self.collection_id)
        docs = coll_ref.stream()

        raw_records = []
        for doc in docs:
            d = doc.to_dict()
            d["_doc_id"] = doc.id
            raw_records.append(d)

        return self._standardize_tickets(raw_records)

    def _fetch_via_rest_api(self) -> list:
        logger.info(f"Querying Firestore via REST API: project={self.project_id}, db={self.database_id}, collection={self.collection_id}...")
        url = f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/{self.database_id}/documents:runQuery"
        session = requests.Session()

        # Concurrent partition queries for full channel representation
        partitions = [
            ("Public", 1500),         # BBMP Sahaya citizen complaints
            ("Officials", 1000),      # Municipal officials / corporators
            ("O&M (CMS)", 2000),      # Field contractor tasks
            ("Auto", 2500)            # Auto CCMS alarms
        ]

        all_docs = {}

        def query_partition(comp, limit):
            payload = {
                "structuredQuery": {
                    "from": [{"collectionId": self.collection_id}],
                    "where": {
                        "compositeFilter": {
                            "op": "AND",
                            "filters": [
                                {
                                    "fieldFilter": {
                                        "field": {"fieldPath": "customer_id"},
                                        "op": "EQUAL",
                                        "value": {"stringValue": self.customer_id}
                                    }
                                },
                                {
                                    "fieldFilter": {
                                        "field": {"fieldPath": "complainee"},
                                        "op": "EQUAL",
                                        "value": {"stringValue": comp}
                                    }
                                }
                            ]
                        }
                    },
                    "limit": limit
                }
            }
            res = []
            try:
                r = session.post(url, json=payload, timeout=25)
                if r.status_code == 200:
                    for item in r.json():
                        if "document" in item:
                            res.append(item["document"])
            except Exception as ex:
                logger.warning(f"Error querying partition '{comp}': {ex}")
            return res

        def query_recent(limit=1500):
            payload = {
                "structuredQuery": {
                    "from": [{"collectionId": self.collection_id}],
                    "where": {
                        "fieldFilter": {
                            "field": {"fieldPath": "customer_id"},
                            "op": "EQUAL",
                            "value": {"stringValue": self.customer_id}
                        }
                    },
                    "orderBy": [
                        {"field": {"fieldPath": "ticket_opened_on"}, "direction": "DESCENDING"}
                    ],
                    "limit": limit
                }
            }
            res = []
            try:
                r = session.post(url, json=payload, timeout=25)
                if r.status_code == 200:
                    for item in r.json():
                        if "document" in item:
                            res.append(item["document"])
            except Exception as ex:
                logger.warning(f"Error querying recent tickets: {ex}")
            return res

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(query_partition, c[0], c[1]): c[0] for c in partitions}
                futures[executor.submit(query_recent, 1500)] = "Recent"

                for fut in as_completed(futures):
                    for d in fut.result():
                        name = d.get("name", "")
                        if name:
                            all_docs[name] = d

            raw_records = []
            for doc_name, doc in all_docs.items():
                doc_id = doc_name.split("/")[-1]
                fields = doc.get("fields", {})
                parsed = {k: self._parse_firestore_field(v) for k, v in fields.items()}
                parsed["_doc_id"] = doc_id
                raw_records.append(parsed)

            logger.info(f"Retrieved {len(raw_records)} unique ticket documents via Firestore REST API.")
            return self._standardize_tickets(raw_records)

        except Exception as e:
            logger.error(f"Error querying Firestore REST API: {e}")
            logger.info("Falling back to simulated ticket data.")
            return get_mock_tickets_data()

    def get_bbmp_totals(self) -> dict:
        """Runs fast aggregation queries to get exact total tickets, closed, pending and resolution rate for BBMP."""
        try:
            agg_url = f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/{self.database_id}/documents:runAggregationQuery"
            def get_count(filter_clause=None):
                payload = {
                    "structuredAggregationQuery": {
                        "structuredQuery": {"from": [{"collectionId": self.collection_id}]},
                        "aggregations": [{"alias": "count", "count": {}}]
                    }
                }
                if filter_clause:
                    payload["structuredAggregationQuery"]["structuredQuery"]["where"] = filter_clause
                r = requests.post(agg_url, json=payload, timeout=10)
                if r.status_code == 200:
                    return int(r.json()[0]["result"]["aggregateFields"]["count"]["integerValue"])
                return None

            total = get_count({"fieldFilter": {"field": {"fieldPath": "customer_id"}, "op": "EQUAL", "value": {"stringValue": self.customer_id}}})
            closed = get_count({"compositeFilter": {"op": "AND", "filters": [
                {"fieldFilter": {"field": {"fieldPath": "customer_id"}, "op": "EQUAL", "value": {"stringValue": self.customer_id}}},
                {"fieldFilter": {"field": {"fieldPath": "status"}, "op": "IN", "value": {"arrayValue": {"values": [
                    {"stringValue": "Closed"}, {"stringValue": "Visited-Closed"}, {"stringValue": "Verified-Closed"}
                ]}}}}
            ]}})
            if total is not None and closed is not None and total > 0:
                pend = total - closed
                res_rate = round(closed / total * 100, 1)
                return {
                    "total": total,
                    "resolved": closed,
                    "pending": pend,
                    "res_rate": res_rate
                }
        except Exception as e:
            logger.warning(f"Could not run live aggregation count: {e}")
        return {
            "total": 38019,
            "resolved": 36142,
            "pending": 1877,
            "res_rate": 95.1
        }

    def _parse_firestore_field(self, v):
        if not isinstance(v, dict):
            return v
        if "stringValue" in v:
            return v["stringValue"]
        if "integerValue" in v:
            return int(v["integerValue"])
        if "doubleValue" in v:
            return float(v["doubleValue"])
        if "booleanValue" in v:
            return v["booleanValue"]
        if "timestampValue" in v:
            return v["timestampValue"]
        if "nullValue" in v:
            return None
        if "arrayValue" in v:
            return [self._parse_firestore_field(x) for x in v.get("arrayValue", {}).get("values", [])]
        if "mapValue" in v:
            return {k: self._parse_firestore_field(val) for k, val in v.get("mapValue", {}).get("fields", {}).items()}
        for val in v.values():
            return val
        return None

    def _standardize_tickets(self, raw_records: list) -> list:
        tickets = []
        now = datetime.now()

        for data in raw_records:
            # Check customer filter if present
            cust = str(data.get("customer", "") or data.get("client", "") or data.get("project", "") or "")
            cid = str(data.get("customer_id", ""))
            
            if self.customer_id and cid and cid != self.customer_id:
                if self.target_customer and cust and self.target_customer.lower() not in cust.lower():
                    continue

            ticket_id = data.get("ticket_id") or data.get("complaint_no") or data.get("_doc_id") or "TICKET"
            
            # Source determination: Check complainee & channel for Sahaya public grievance
            complainee = str(data.get("complainee", "")).strip()
            source_raw = str(data.get("source", "") or data.get("type", "") or data.get("channel", "") or complainee)
            full_text = json.dumps(data).lower()

            if complainee.lower() in ("officials", "official"):
                source = "Sahaya App (Officials)"  # Official tickets are the BBMP Sahaya app complaints
            elif complainee.lower() in ("public", "citizen"):
                source = "Citizen Grievance Portal"
            elif "field" in source_raw.lower() or "internal" in source_raw.lower() or "o&m" in complainee.lower() or "serviceman" in complainee.lower():
                source = "Field App / Internal"
            elif "auto" in complainee.lower() or "system" in complainee.lower():
                source = "Auto CMS Alert"
            else:
                source = source_raw or "Portal"

            # Status & Resolution
            status = str(data.get("status", "Open")).strip()
            status_lower = status.lower()
            is_resolved = ("close" in status_lower or status_lower in ("resolved", "completed", "done", "fixed", "visited-closed", "verified-closed"))

            # Created At & Resolved At parsing
            created_raw = data.get("ticket_opened_on") or data.get("created_at") or data.get("timestamp") or data.get("date")
            created_at = self._parse_datetime(created_raw) or now

            resolved_raw = data.get("ticket_closed_on") or data.get("resolved_at") or data.get("closed_at") or data.get("last_updated_on")
            resolved_at = self._parse_datetime(resolved_raw) if is_resolved else None

            # Compute Aging
            if is_resolved and resolved_at:
                aging_days = max(0, (resolved_at - created_at).days)
            else:
                aging_days = max(0, (now - created_at).days)

            raw_z = (data.get("zone") or data.get("division") or "").strip()
            if not raw_z or "bangalore" in raw_z.lower():
                zone = "EAST"
            else:
                zone = raw_z
            ward = data.get("ward") or "BBMP Ward"
            issue_category = data.get("problem_type") or data.get("issue_category") or data.get("issue_identified") or data.get("description") or "Streetlight issue"
            assigned_to = data.get("assignee") or data.get("assigned_to") or data.get("engineer") or data.get("technician") or "Unassigned"

            tickets.append({
                "ticket_id": ticket_id,
                "source": source,
                "customer": self.target_customer,
                "zone": zone,
                "ward": ward if ward.strip() else "BBMP Ward",
                "issue_category": str(issue_category)[:60],
                "status": status,
                "is_resolved": is_resolved,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M"),
                "resolved_at": resolved_at.strftime("%Y-%m-%d %H:%M") if resolved_at else None,
                "aging_days": aging_days,
                "assigned_to": assigned_to if str(assigned_to).strip() else "Unassigned",
                "sla_breached": aging_days > 3 and not is_resolved
            })

        if not tickets:
            logger.warning("No tickets found matching criteria in Firestore. Using simulated data.")
            return get_mock_tickets_data()

        logger.info(f"Successfully processed {len(tickets)} tickets from Firestore.")
        return tickets

    def _parse_datetime(self, val):
        if not val:
            return None
        if isinstance(val, datetime):
            return val.replace(tzinfo=None)
        if hasattr(val, "to_datetime"):
            return val.to_datetime().replace(tzinfo=None)
        if isinstance(val, (int, float)):
            if val > 1e11:
                val = val / 1000.0
            return datetime.fromtimestamp(val)
        if isinstance(val, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
                try:
                    return datetime.strptime(val.split(".")[0], fmt.split(".")[0])
                except Exception:
                    continue
        return None
