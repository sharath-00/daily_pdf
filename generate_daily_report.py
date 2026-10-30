"""
Main Entrypoint Script: Daily Operations & Standup Review PDF Report Generator.
Orchestrates ThingsBoard telemetry collection, Firebase ticket data extraction,
advanced analytics, and executive PDF generation.
"""
import sys
import argparse
import logging
from config import Config
from thingsboard_client import ThingsBoardClient
from firebase_client import FirebaseClient
from google_sheets_client import GoogleSheetsClient
from analytics import AnalyticsEngine
from pdf_generator import ReportGenerator
from email_sender import EmailSender

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DailyReportOrchestrator")

def main():
    parser = argparse.ArgumentParser(description="Generate Daily Operations Review PDF Report for Standup Meetings.")
    parser.add_argument("--output", "-o", default=Config.OUTPUT_PDF_PATH, help="Output PDF file path")
    parser.add_argument("--mock", action="store_true", help="Force using mock telemetry and ticket data")
    parser.add_argument("--email", action="store_true", help="Send the generated PDF report via email")
    args = parser.parse_args()

    if args.mock:
        Config.FORCE_MOCK_DATA = True

    print("\n" + "="*70)
    print("  SCHNELL ENERGY EQUIPMENTS - DAILY OPERATIONS REPORT GENERATOR")
    print("  Customer: " + Config.TARGET_CUSTOMER)
    print("="*70 + "\n")

    # 1. Fetch Telemetry Data
    logger.info("Step 1/5: Fetching CCMS panel telemetry from ThingsBoard (real-time)...")
    tb_client = ThingsBoardClient()
    panels = tb_client.fetch_panels_telemetry()
    logger.info(f"Loaded {len(panels)} panel records.")

    # 2. Fetch Tickets Data
    logger.info("Step 2/5: Fetching grievance tickets from Firebase Firestore (real-time)...")
    fb_client = FirebaseClient()
    tickets = fb_client.fetch_tickets()
    bbmp_totals = fb_client.get_bbmp_totals()
    logger.info(f"Loaded {len(tickets)} ticket records. BBMP Totals: {bbmp_totals['total']} (Resolved: {bbmp_totals['resolved']}, Pending: {bbmp_totals['pending']}, Rate: {bbmp_totals['res_rate']}%)")

    # 3. Fetch Materials Inventory from Google Sheet (STOCK(PROJECT))
    logger.info("Step 3/5: Fetching store materials inventory from Google Sheet (STOCK(PROJECT))...")
    gs_client = GoogleSheetsClient()
    materials_data = gs_client.fetch_bbmp_store_stock_project()
    if materials_data.get("status") == "SUCCESS":
        logger.info(f"Loaded {materials_data['total_materials']} material items from Google Sheet. Austin 0-stock: {len(materials_data['zero_austin'])}, Hebbal: {len(materials_data['zero_hebbal'])}, Bommasandra: {len(materials_data['zero_bommasandra'])}, Citywide Out-of-Stock: {len(materials_data['zero_all'])}.")
    else:
        logger.warning(f"Google Sheet notice: {materials_data.get('error')}")

    # 4. Perform Analytics
    logger.info("Step 4/5: Analyzing offline panels, Sahaya resolution rates, and chronic escalations...")
    engine = AnalyticsEngine(panels, tickets, bbmp_totals=bbmp_totals, materials_data=materials_data)
    insights = engine.analyze_all(materials_data=materials_data)

    telem = insights["telemetry"]
    tix = insights["tickets"]

    # 5. Generate Executive PDF
    output_file = args.output
    logger.info(f"Step 5/5: Generating publication-grade executive PDF to '{output_file}'...")
    generator = ReportGenerator(insights, materials_data=materials_data, output_path=output_file)
    pdf_path = generator.build_pdf()

    # 5. Print Executive Console Summary
    print("\n" + "-"*70)
    print("  DAILY MEETING EXECUTIVE SUMMARY PREVIEW")
    print("-"*70)
    print(f"  * Total CCMS Panels Monitored : {telem['total_panels']} ({telem['online_pct']}% Online)")
    print(f"  * Chronic Offline Panels (>7D): {telem['chronic_panels_count']} panels ({telem['chronic_of_offline_pct']}% of offline)")
    print(f"  * Sahaya Complaints Total     : {tix['sahaya_total']}")
    print(f"  * Sahaya Resolution Rate      : {tix['sahaya_res_rate']}% [{tix['sahaya_rating']}]")
    print(f"  * Sahaya Avg Turnaround Time  : {tix['sahaya_avg_tat_days']} days")
    print(f"  * Overdue Unresolved Tickets  : {len(tix['chronic_unresolved'])} tickets > {Config.LONG_PENDING_TICKET_DAYS} days")
    
    print("\n  KEY TALKING POINTS FOR TODAY'S MEETING:")
    for i, pt in enumerate(insights["meeting_points"], 1):
        clean_title = pt['title'].encode('ascii', 'replace').decode('ascii')
        clean_detail = pt['detail'][:110].encode('ascii', 'replace').decode('ascii')
        print(f"    [{i}] {clean_title}")
        print(f"        -> {clean_detail}...")

    print("\n" + "="*70)
    print(f"  SUCCESS: Executive PDF generated at -> {pdf_path}")
    print("="*70 + "\n")

    # 6. Optional Email Dispatch
    if args.email or Config.ENABLE_EMAIL:
        logger.info("Email dispatch enabled. Sending executive PDF to configured recipients...")
        mailer = EmailSender()
        mailer.send_report_email(pdf_path=pdf_path, insights=insights, materials_data=materials_data)

    return 0

if __name__ == "__main__":
    sys.exit(main())
