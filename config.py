import os
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

class Config:
    # ThingsBoard Settings
    THINGSBOARD_URL = os.getenv("THINGSBOARD_URL", "https://schnelliot.in").rstrip("/")
    THINGSBOARD_USERNAME = os.getenv("THINGSBOARD_USERNAME", "vinoth.joel@schnellenergy.com")
    THINGSBOARD_PASSWORD = os.getenv("THINGSBOARD_PASSWORD", "vinoth555")
    THINGSBOARD_DEVICE_TYPE = os.getenv("THINGSBOARD_DEVICE_TYPE", "CCMS") # or Panel, default empty to query all
    BBMP_CUSTOMER_ID = os.getenv("BBMP_CUSTOMER_ID", "e2119df0-45c3-11f0-94dc-77130b2f47e9")
    
    # Firebase Settings
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "schnelliot-380113")
    FIREBASE_DATABASE_ID = os.getenv("FIREBASE_DATABASE_ID", "smartlights")
    FIREBASE_COLLECTION_ID = os.getenv("FIREBASE_COLLECTION_ID", "tickets")
    TARGET_CUSTOMER = os.getenv("TARGET_CUSTOMER", "Bangalore (BBMP)")
    
    # Firebase Service Account (Can be a file path or raw JSON string for GitHub Secrets)
    FIREBASE_SERVICE_ACCOUNT_KEY = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "")
    FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    
    # Analysis Thresholds
    OFFLINE_DAYS_THRESHOLD = int(os.getenv("OFFLINE_DAYS_THRESHOLD", "7"))
    LONG_PENDING_TICKET_DAYS = int(os.getenv("LONG_PENDING_TICKET_DAYS", "7"))
    
    # Telemetry Filtering & Exclusion Settings
    # If False, includes all offline panels in chronic reports (true live total, no hidden panels)
    EXCLUDE_PF_PANELS = os.getenv("EXCLUDE_PF_PANELS", "false").lower() in ("true", "1", "yes")
    
    # Mode Settings
    # If True, forces mock data generator; if False, attempts live APIs and falls back if credentials missing/invalid
    FORCE_MOCK_DATA = os.getenv("FORCE_MOCK_DATA", "false").lower() in ("true", "1", "yes")
    
    # PDF Output Settings
    OUTPUT_PDF_PATH = os.getenv("OUTPUT_PDF_PATH", "daily_meeting_operations_report.pdf")
    REPORT_TITLE = os.getenv("REPORT_TITLE", "Daily Operations & Telemetry Review")
    ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "Schnell Energy Equipments")
    
    # Email (SMTP) Settings
    ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "true").lower() in ("true", "1", "yes")
    SMTP_HOST = os.getenv("SMTP_SERVER", os.getenv("SMTP_HOST", "smtp.gmail.com"))
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
    EMAIL_SENDER = os.getenv("SENDER_EMAIL", os.getenv("EMAIL_SENDER", ""))
    _raw_recipients = os.getenv("RECIPIENTS", os.getenv("EMAIL_RECIPIENTS", ""))
    EMAIL_RECIPIENTS = [r.strip() for r in _raw_recipients.split(",") if r.strip()]
    EMAIL_CC = [c.strip() for c in os.getenv("EMAIL_CC", "").split(",") if c.strip()]
    EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Daily Operations & Telemetry Review - Bangalore (BBMP)")
