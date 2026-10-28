import json
import os
import pymupdf
from analytics import AnalyticsEngine
from google_sheets_client import GoogleSheetsClient
from pdf_generator import ReportGenerator

print("Loading cached telemetry & tickets...")
with open("bbmp_realtime_data.json", "r", encoding="utf-8") as f:
    panels = json.load(f)

with open("bbmp_tickets_data.json", "r", encoding="utf-8") as f:
    tickets = json.load(f)

bbmp_totals = {
    "total": 38019,
    "resolved": 36143,
    "pending": 1876,
    "res_rate": 95.1
}

print(f"Loaded {len(panels)} panels and {len(tickets)} tickets.")

print("Fetching Google Sheets stock...")
sheets_client = GoogleSheetsClient()
materials_data = sheets_client.fetch_bbmp_store_stock_project()

print("Running analytics...")
engine = AnalyticsEngine(panels, tickets, bbmp_totals=bbmp_totals, materials_data=materials_data)
insights = engine.analyze_all(materials_data=materials_data)

print("Generating PDF...")
generator = ReportGenerator(insights, materials_data=materials_data, output_path="daily_meeting_operations_report.pdf")
out_path = generator.build_pdf()
print(f"Generated: {out_path}")

doc = pymupdf.open(out_path)
page_count = len(doc)
print(f"SUCCESS: Generated {page_count}-page executive report at {out_path}")
