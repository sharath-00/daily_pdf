"""
Google Sheets Client for Materials Inventory Integration.
Reads materials inventory counts using service account credentials (service.json)
and flags items with 0 stock / depleted inventory for daily standup escalation.
"""
import os
import json
import logging
from typing import Dict, List, Any
import gspread
from google.oauth2.service_account import Credentials
from config import Config

logger = logging.getLogger("GoogleSheetsClient")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

class GoogleSheetsClient:
    def __init__(self, service_account_file: str = "service.json", spreadsheet_id_or_url: str = None):
        self.service_account_file = service_account_file
        self.spreadsheet_id_or_url = spreadsheet_id_or_url or os.getenv("GOOGLE_SHEET_ID_OR_URL", "")
        self.client = None

    def authenticate(self) -> bool:
        # Check if environment variable contains the JSON credentials (e.g. from GitHub Secrets)
        env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if env_json:
            try:
                info = json.loads(env_json)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                self.client = gspread.authorize(creds)
                logger.info("Successfully authenticated with Google Sheets API via GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
                return True
            except Exception as e:
                logger.warning(f"Failed to authenticate using GOOGLE_SERVICE_ACCOUNT_JSON env variable: {e}")

        if not os.path.exists(self.service_account_file):
            logger.warning(f"Service account file '{self.service_account_file}' not found.")
            return False

        try:
            creds = Credentials.from_service_account_file(self.service_account_file, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            logger.info("Successfully authenticated with Google Sheets API.")
            return True
        except Exception as e:
            logger.error(f"Error authenticating with Google Sheets API: {e}")
            return False

    def fetch_materials_inventory(self, sheet_name_or_index: Any = 0) -> Dict[str, Any]:
        """
        Fetches materials records from Google Sheets.
        Identifies zero-stock items (count == 0) and formats an operational summary.
        """
        if not self.client:
            if not self.authenticate():
                return self._fallback_empty_inventory("Service account credentials not provided")

        if not self.spreadsheet_id_or_url:
            return self._fallback_empty_inventory("Spreadsheet ID or URL not specified")

        try:
            if self.spreadsheet_id_or_url.startswith("https://"):
                sheet = self.client.open_by_url(self.spreadsheet_id_or_url)
            else:
                sheet = self.client.open_by_key(self.spreadsheet_id_or_url)

            worksheet = sheet.get_worksheet(sheet_name_or_index) if isinstance(sheet_name_or_index, int) else sheet.worksheet(sheet_name_or_index)
            records = worksheet.get_all_records()
            logger.info(f"Retrieved {len(records)} material rows from Google Sheet: '{sheet.title}'")

            return self._process_material_records(records, sheet.title)

        except Exception as e:
            logger.error(f"Failed to fetch materials from Google Sheet: {e}")
            return self._fallback_empty_inventory(str(e))

    def fetch_bbmp_store_stock_project(self, spreadsheet_id: str = "1uNZoNaLSNngWCdkig8tIUDv_gkD71jeyfpSRD8z3fQc", worksheet_name: str = "STOCK(PROJECT)") -> Dict[str, Any]:
        """
        Parses the BBMP Store 'STOCK(PROJECT)' tab.
        Extracts current stock for:
        - Bommasandra (Col 8)
        - Austin Road (Col 13)
        - Hebbal (Col 18)
        - Total Stock (Col 19)
        Identifies all materials with 0 count at each store.
        """
        if not self.client and not self.authenticate():
            return self._fallback_empty_inventory("Service account authentication failed")

        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            ws = sheet.worksheet(worksheet_name)
            rows = ws.get_all_values()

            def parse_val(v):
                v_clean = str(v).replace(",", "").strip()
                if not v_clean or v_clean == "":
                    return 0
                try:
                    return float(v_clean)
                except Exception:
                    return 0

            materials = []
            for idx in range(4, len(rows)):
                r = rows[idx]
                if len(r) < 20:
                    continue
                sl = r[0].strip()
                mat = r[1].strip()
                unit = r[2].strip() if len(r) > 2 else "Nos"
                if not mat or mat.lower() == "total" or "updated" in mat.lower():
                    continue

                bommasandra_stock = int(parse_val(r[8]))
                austin_stock = int(parse_val(r[13]))
                hebbal_stock = int(parse_val(r[18]))
                total_stock = int(parse_val(r[19]))

                materials.append({
                    "sl": sl,
                    "material": mat,
                    "unit": unit,
                    "bommasandra_stock": bommasandra_stock,
                    "austin_stock": austin_stock,
                    "hebbal_stock": hebbal_stock,
                    "total_stock": total_stock
                })

            zero_austin = [m for m in materials if m["austin_stock"] == 0]
            zero_hebbal = [m for m in materials if m["hebbal_stock"] == 0]
            zero_bommasandra = [m for m in materials if m["bommasandra_stock"] == 0]
            zero_all = [m for m in materials if m["total_stock"] == 0 or (m["bommasandra_stock"] == 0 and m["austin_stock"] == 0 and m["hebbal_stock"] == 0)]

            logger.info(f"STOCK(PROJECT) parsed: {len(materials)} materials | Zero Stock: Austin={len(zero_austin)}, Hebbal={len(zero_hebbal)}, Bommasandra={len(zero_bommasandra)}, Total Depleted={len(zero_all)}")

            return {
                "status": "SUCCESS",
                "sheet_title": sheet.title,
                "worksheet_name": worksheet_name,
                "total_materials": len(materials),
                "materials": materials,
                "zero_austin": zero_austin,
                "zero_austin_names": [m["material"] for m in zero_austin],
                "zero_hebbal": zero_hebbal,
                "zero_hebbal_names": [m["material"] for m in zero_hebbal],
                "zero_bommasandra": zero_bommasandra,
                "zero_bommasandra_names": [m["material"] for m in zero_bommasandra],
                "zero_all": zero_all,
                "zero_all_names": [m["material"] for m in zero_all]
            }
        except Exception as e:
            logger.error(f"Error fetching STOCK(PROJECT) tab: {e}")
            return self._fallback_empty_inventory(str(e))

    def _process_material_records(self, records: List[Dict[str, Any]], sheet_title: str) -> Dict[str, Any]:
        zero_stock_items = []
        available_items = []
        all_materials = []

        for row in records:
            # Find column for material name / item description
            name = None
            count = None

            for k, v in row.items():
                k_lower = str(k).strip().lower()
                if any(x in k_lower for x in ["material", "item", "description", "name", "component"]):
                    if not name or "name" in k_lower or "material" in k_lower:
                        name = str(v).strip()
                if any(x in k_lower for x in ["count", "qty", "quantity", "stock", "available", "balance"]):
                    try:
                        clean_v = str(v).replace(",", "").strip()
                        count = float(clean_v) if clean_v else 0
                    except (ValueError, TypeError):
                        count = 0

            # Fallback if specific headers not matched
            if not name and len(row) > 0:
                name = str(list(row.values())[0]).strip()
            if count is None and len(row) > 1:
                try:
                    count = float(list(row.values())[1])
                except Exception:
                    count = 0

            if not name:
                continue

            item_data = {
                "material_name": name,
                "count": int(count) if count == int(count) else count,
                "raw_row": row
            }
            all_materials.append(item_data)

            if count <= 0:
                zero_stock_items.append(item_data)
            else:
                available_items.append(item_data)

        zero_names = [item["material_name"] for item in zero_stock_items]
        logger.info(f"Found {len(zero_stock_items)} zero-stock materials out of {len(all_materials)} total items.")

        return {
            "status": "SUCCESS",
            "sheet_title": sheet_title,
            "total_materials_count": len(all_materials),
            "zero_stock_count": len(zero_stock_items),
            "available_stock_count": len(available_items),
            "zero_stock_materials": zero_stock_items,
            "zero_stock_names": zero_names,
            "available_materials": available_items,
            "all_materials": all_materials
        }

    def _fallback_empty_inventory(self, error_msg: str) -> Dict[str, Any]:
        return {
            "status": "NOT_CONFIGURED",
            "error": error_msg,
            "total_materials_count": 0,
            "zero_stock_count": 0,
            "available_stock_count": 0,
            "zero_stock_materials": [],
            "zero_stock_names": [],
            "available_materials": [],
            "all_materials": []
        }
