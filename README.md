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
├── .github/workflows/
│   └── generate_daily_report.yml # GitHub Actions automated real-time PDF workflow
├── analytics.py                  # Analytics engine (telemetry, grievances, stock, zones)
├── config.py                     # Centralized configuration and threshold settings
├── fetch_bbmp_tickets.py         # Firebase Firestore tickets sync utility
├── fetch_schnell_data.py         # ThingsBoard panel telemetry sync utility
├── firebase_client.py            # Firestore API integration
├── generate_daily_report.py      # Main production orchestration & report generator
├── google_sheets_client.py       # Google Sheets API connector for stock inventory
├── mock_data.py                  # Realistic offline fallback dataset
├── pdf_generator.py              # ReportLab 3-page executive PDF layout engine
├── quick_build_pdf.py            # Rapid local PDF generation using cached data
├── requirements.txt              # Python package dependencies
├── schnell_logo.jpg              # Corporate branding asset
├── .env.example                  # Template for required environment variables
└── .gitignore                    # Excludes secrets, PDFs, and local JSON caches
```

---

## GitHub Actions & External API Dispatch

The report generation workflow is located at [`.github/workflows/generate_daily_report.yml`](.github/workflows/generate_daily_report.yml). Every execution automatically fetches **fresh real-time data** directly from ThingsBoard, Firebase, and Google Sheets (no cached data).

### 1. Trigger via External API (`repository_dispatch`)

You can trigger the workflow from any external backend, webhook, or cron script using GitHub's REST API:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_GITHUB_PAT" \
  https://api.github.com/repos/sharath-00/daily_pdf/dispatches \
  -d '{"event_type": "generate_pdf"}'
```

*(Note: `YOUR_GITHUB_PAT` requires `repo` or `contents:write` permission).*

### 2. Trigger via Python Script

```python
import requests

GITHUB_TOKEN = "your_github_token"
REPO = "sharath-00/daily_pdf"

url = f"https://api.github.com/repos/{REPO}/dispatches"
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}
payload = {"event_type": "generate_pdf"}

response = requests.post(url, json=payload, headers=headers)
if response.status_code == 204:
    print("Workflow dispatched successfully!")
else:
    print(f"Failed to dispatch: {response.status_code} - {response.text}")
```

### 3. Trigger via Node.js / Fetch

```javascript
await fetch("https://api.github.com/repos/sharath-00/daily_pdf/dispatches", {
  method: "POST",
  headers: {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer YOUR_GITHUB_PAT",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ event_type: "generate_pdf" })
});
```

### 4. Direct Download Link for Generated PDF
Once the workflow completes, the PDF is automatically published to the `latest` GitHub Release:
- **Direct Download URL:**
  ```
  https://github.com/sharath-00/daily_pdf/releases/download/latest/daily_meeting_operations_report.pdf
  ```
- It is also available under the workflow run's **Artifacts** section (`daily_meeting_operations_report`).

---

## Configuring GitHub Secrets

In your GitHub repository (**Settings > Secrets and variables > Actions > Secrets**), add the following secrets:

| Secret Name | Description | Default / Fallback |
| :--- | :--- | :--- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Entire JSON content of `service.json` for Google Sheets stock data | `service.json` file |
| `THINGSBOARD_URL` | Base URL of ThingsBoard instance | `https://schnelliot.in` |
| `THINGSBOARD_USERNAME` | ThingsBoard operator account | Configured in `config.py` |
| `THINGSBOARD_PASSWORD` | ThingsBoard operator password | Configured in `config.py` |
| `BBMP_CUSTOMER_ID` | BBMP Customer UUID | `e2119df0-45c3-11f0-94dc-77130b2f47e9` |

---

## Local Installation & Setup

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
