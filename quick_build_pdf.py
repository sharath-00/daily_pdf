"""
PDF Report Generator Script.
Always fetches real-time data from ThingsBoard, Firebase Firestore, and Google Sheets.
Zero cached data is used.
"""
import sys
import logging
import pymupdf
from config import Config
from thingsboard_client import ThingsBoardClient
from firebase_client import FirebaseClient
from google_sheets_client import GoogleSheetsClient
from analytics import AnalyticsEngine
from pdf_generator import ReportGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BuildPDF")

def build_pdf():
    print("\n" + "="*70)
    print("  FETCHING REAL-TIME DATA & GENERATING EXECUTIVE PDF REPORT")
    print("  (Zero cached data - live queries to ThingsBoard, Firebase & Sheets)")
    print("="*70 + "\n")

    # 1. Fetch real-time telemetry from ThingsBoard
    logger.info("Step 1/4: Fetching live CCMS panel telemetry from ThingsBoard...")
    tb = ThingsBoardClient()
    panels = tb.fetch_panels_telemetry()
    logger.info(f"Retrieved {len(panels)} live CCMS panels from ThingsBoard.")

    # 2. Fetch real-time grievance tickets & totals from Firebase Firestore
    logger.info("Step 2/4: Fetching live grievance tickets from Firebase Firestore...")
    fb = FirebaseClient()
    tickets = fb.fetch_tickets()
    bbmp_totals = fb.get_bbmp_totals()
    logger.info(f"Retrieved {len(tickets)} live tickets. BBMP Totals: {bbmp_totals['total']} (Resolved: {bbmp_totals['resolved']}, Pending: {bbmp_totals['pending']}, Rate: {bbmp_totals['res_rate']}%)")

    # 3. Fetch real-time store stock from Google Sheets
    logger.info("Step 3/4: Fetching store materials stock from Google Sheets (STOCK(PROJECT))...")
    sheets_client = GoogleSheetsClient()
    materials_data = sheets_client.fetch_bbmp_store_stock_project()
    if materials_data.get("status") == "SUCCESS":
        logger.info(f"Retrieved {materials_data.get('total_materials', 0)} inventory items from Google Sheets.")
    else:
        logger.warning(f"Google Sheets warning: {materials_data.get('error')}")

    # 4. Analytics & PDF generation
    logger.info("Step 4/4: Running analytics and generating executive PDF...")
    engine = AnalyticsEngine(panels, tickets, bbmp_totals=bbmp_totals, materials_data=materials_data)
    insights = engine.analyze_all(materials_data=materials_data)

    output_path = Config.OUTPUT_PDF_PATH
    generator = ReportGenerator(insights, materials_data=materials_data, output_path=output_path)
    out_path = generator.build_pdf()

    doc = pymupdf.open(out_path)
    page_count = len(doc)
    print("\n" + "="*70)
    print(f"  SUCCESS: Generated {page_count}-page executive report with fresh live data at:")
    print(f"  {out_path}")
    print("="*70 + "\n")

    # 5. Optional Email Dispatch
    if Config.ENABLE_EMAIL:
        logger.info("Email dispatch enabled (ENABLE_EMAIL=true). Sending executive PDF...")
        from email_sender import EmailSender
        mailer = EmailSender()
        mailer.send_report_email(pdf_path=out_path, insights=insights, materials_data=materials_data)

    return out_path

if __name__ == "__main__":
    build_pdf()
