# BBMP Smart Lighting - Daily Operations & Telemetry Review Generator

Automated executive daily reporting system for the BBMP (Bruhat Bengaluru Mahanagara Palike) CCMS Smart Streetlighting project operated by Schnell Energy Equipments.

## Overview
This system orchestrates real-time IoT telemetry from **ThingsBoard**, grievance tickets from **Firebase Firestore**, and store inventory from **Google Sheets** to generate a publication-grade 3-page executive PDF report for daily operational standup meetings with municipal executive engineers.

---

## Key Features

1. **Executive KPI Dashboard & Standup Talking Points:**
   - Total CCMS panels monitored and real-time connectivity rate.
   - Chronic offline panels (> 7 days uncommunicated).
   - Sahaya official app grievance redressal metrics, TAT, and pending backlogs.
   - Citywide store inventory deficit alerts.

2. **Grievance Redressal Performance:**
   - Cumulative BBMP ticket resolution rates.
   - Dedicated breakdown for BBMP Sahaya Official App complaints.

3. **Store Materials Deficit & Zero-Stock Escalation:**
   - Real-time stockout tracking across Central Warehouse (Bommasandra) and depot stores (Austin Road, Hebbal).

4. **Zone-wise CCMS Telemetry Infrastructure Breakdown:**
   - Granular breakdown for physical operational regions:
     - **EAST Region**
     - **Bommanahalli Region**
   - Detailed aging distribution (`7–14d`, `14–30d`, `>30d`), max uncommunicated duration, and primary field diagnostic actions.

5. **Zone-wise Sahaya App Official Tickets Breakdown:**
   - Breakdown across municipal divisions:
     - `SarvagnaNagar`, `PulakeshiNagar`, `ShanthiNagar`, `ShivajiNagar`, `CVRamanNagar`, `Bommanahali-Z1`, and `EAST`.
   - Resolution rates, SLA status, and assigned vendor/contractor accountability.

6. **Store Materials Stock Inventory Report:**
   - Complete itemized physical inventory table covering all 43 standard CCMS electrical materials across Bommasandra, Austin Road, and Hebbal depots.
   - Status indicators (`HEALTHY`, `DEFICIT`, `DEPLETED`) with store deficit summary.

---

## Repository Structure

```
├── analytics.py             # Analytics engine (telemetry, grievances, stock, zones)
├── config.py                # Centralized configuration and threshold settings
├── fetch_bbmp_tickets.py    # Firebase Firestore tickets sync utility
├── fetch_schnell_data.py    # ThingsBoard panel telemetry sync utility
├── firebase_client.py       # Firestore API integration
├── generate_daily_report.py # Main production orchestration & report generator
├── google_sheets_client.py  # Google Sheets API connector for stock inventory
├── mock_data.py             # Realistic offline fallback dataset
├── pdf_generator.py         # ReportLab 3-page executive PDF layout engine
├── quick_build_pdf.py       # Rapid local PDF generation using cached data
├── requirements.txt         # Python package dependencies
├── schnell_logo.jpg         # Corporate branding asset
├── .env.example             # Template for required environment variables
└── .gitignore               # Excludes secrets, PDFs, and local JSON caches
```

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/sharath-00/daily_pdf.git
cd daily_pdf
```

### 2. Set up virtual environment & dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in the required credentials:
```bash
cp .env.example .env
```
Provide the Google Cloud service account JSON file as `service.json` in the root directory for Google Sheets stock synchronization.

---

## Usage

### Generate Full Executive Report (Live Data)
Fetches live telemetry from ThingsBoard, live tickets from Firebase Firestore, and inventory from Google Sheets:
```bash
python generate_daily_report.py
```

### Run with Mock / Simulated Data
```bash
python generate_daily_report.py --mock
```

### Quick Local Build (Cached Data)
```bash
python quick_build_pdf.py
```

---

## License
Proprietary - Schnell Energy Equipments Pvt. Ltd.
