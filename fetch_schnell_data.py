"""
Script to fetch real-time data from Schnell IoT (ThingsBoard) for Bangalore (BBMP) Project.
Fetches all CCMS panels, device attributes, connectivity status, and electrical telemetry.
Saves data to JSON and CSV files and prints an executive summary.
"""
import os
import json
import csv
import time
import logging
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SchnellBBMPFetcher")

def fetch_schnell_bbmp_data(output_json="bbmp_realtime_data.json", output_csv="bbmp_realtime_summary.csv"):
    base_url = Config.THINGSBOARD_URL
    username = Config.THINGSBOARD_USERNAME
    password = Config.THINGSBOARD_PASSWORD
    customer_id = Config.BBMP_CUSTOMER_ID

    print("\n" + "="*75)
    print("  SCHNELL IoT - BANGALORE (BBMP) REAL-TIME DATA INGESTION")
    print(f"  Server URL   : {base_url}")
    print(f"  Customer ID  : {customer_id}")
    print(f"  User Account : {username}")
    print("="*75 + "\n")

    # 1. Authenticate with ThingsBoard
    logger.info("Authenticating with Schnell IoT API...")
    login_resp = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    if login_resp.status_code != 200:
        logger.error(f"Authentication failed: HTTP {login_resp.status_code} - {login_resp.text}")
        return None

    token = login_resp.json().get("token")
    headers = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {token}"
    }
    logger.info("Authentication successful. JWT token acquired.")

    # 2. Fetch all BBMP Customer Devices
    logger.info(f"Querying all BBMP devices from customer endpoint...")
    all_devices = []
    page = 0
    page_size = 1000

    while True:
        url = f"{base_url}/api/customer/{customer_id}/deviceInfos?pageSize={page_size}&page={page}"
        resp = requests.get(url, headers=headers, timeout=25)
        if resp.status_code != 200:
            logger.warning(f"Error fetching page {page}: HTTP {resp.status_code}")
            break
        data = resp.json()
        batch = data.get("data", [])
        all_devices.extend(batch)
        logger.info(f"  -> Page {page}: Retrieved {len(batch)} devices (Cumulative: {len(all_devices)})")
        if not data.get("hasNext") or len(batch) == 0:
            break
        page += 1

    total_devices = len(all_devices)
    logger.info(f"Total devices retrieved for BBMP: {total_devices}")

    # 3. Batch Query Server/Shared Attributes & Latest Telemetry via entitiesQuery/find
    logger.info("Batch-fetching server attributes & telemetry for all devices...")
    batch_size = 500
    batches = [all_devices[i:i + batch_size] for i in range(0, total_devices, batch_size)]
    attr_telemetry_cache = {}

    def query_batch(b):
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
                # Server Scope Attributes
                {"type": "SERVER_ATTRIBUTE", "key": "active"},
                {"type": "SERVER_ATTRIBUTE", "key": "lastActivityTime"},
                {"type": "SERVER_ATTRIBUTE", "key": "lastConnectTime"},
                {"type": "SERVER_ATTRIBUTE", "key": "lastDisconnectTime"},
                {"type": "SERVER_ATTRIBUTE", "key": "wardName"},
                {"type": "SERVER_ATTRIBUTE", "key": "zoneName"},
                {"type": "SERVER_ATTRIBUTE", "key": "region"},
                {"type": "SERVER_ATTRIBUTE", "key": "location"},
                {"type": "SERVER_ATTRIBUTE", "key": "gsmProvider"},
                {"type": "SERVER_ATTRIBUTE", "key": "simName"},
                {"type": "SERVER_ATTRIBUTE", "key": "operatingMode"},
                {"type": "SERVER_ATTRIBUTE", "key": "condition"},
                # Shared Scope Attributes
                {"type": "SHARED_ATTRIBUTE", "key": "wardName"},
                {"type": "SHARED_ATTRIBUTE", "key": "zoneName"},
                {"type": "SHARED_ATTRIBUTE", "key": "region"},
                {"type": "SHARED_ATTRIBUTE", "key": "location"},
                # Real-Time Telemetry Timeseries
                {"type": "TIME_SERIES", "key": "systime"},
                {"type": "TIME_SERIES", "key": "rv"},
                {"type": "TIME_SERIES", "key": "yv"},
                {"type": "TIME_SERIES", "key": "bv"},
                {"type": "TIME_SERIES", "key": "ri"},
                {"type": "TIME_SERIES", "key": "yi"},
                {"type": "TIME_SERIES", "key": "bi"},
                {"type": "TIME_SERIES", "key": "tkw"},
                {"type": "TIME_SERIES", "key": "kwh"},
                {"type": "TIME_SERIES", "key": "freq"},
                {"type": "TIME_SERIES", "key": "rssi"},
                {"type": "TIME_SERIES", "key": "faultCode"},
                {"type": "TIME_SERIES", "key": "pkt"}
            ]
        }
        res = {}
        try:
            r = requests.post(f"{base_url}/api/entitiesQuery/find", json=payload, headers=headers, timeout=25)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    eid = item.get("entityId", {}).get("id")
                    latest = item.get("latest", {})
                    combined = {}
                    for scope in ("SERVER_ATTRIBUTE", "SHARED_ATTRIBUTE", "CLIENT_ATTRIBUTE", "TIME_SERIES"):
                        for k, v in latest.get(scope, {}).items():
                            combined[k] = v.get("value")
                    res[eid] = combined
        except Exception as e:
            logger.warning(f"Batch query exception: {e}")
        return res

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(query_batch, b) for b in batches]
        for f in as_completed(futures):
            attr_telemetry_cache.update(f.result())

    logger.info(f"Attributes and telemetry cached for {len(attr_telemetry_cache)} devices.")

    # 4. Standardize and Process All Records
    now_ms = time.time() * 1000
    now_dt = datetime.now()
    panels_data = []

    for dev in all_devices:
        dev_id = dev.get("id", {}).get("id")
        meter_id = dev.get("name", "Unknown")
        feeder_label = dev.get("label", meter_id)
        device_type = dev.get("type", "semc")
        groups = dev.get("groups", [])

        attrs = attr_telemetry_cache.get(dev_id, {})

        # Zone determination
        zone = attrs.get("zoneName") or attrs.get("region")
        if not zone and groups:
            g_name = groups[0].get("name", "").strip()
            if g_name and "park" not in g_name.lower():
                zone = g_name
        # Standardize zone names into the two official BBMP regions: EAST Region and Bommanahalli Region
        z_check = (str(zone or "") + " " + str(meter_id) + " " + str(feeder_label)).lower()
        if "bommanahalli" in z_check or "bommanahali" in z_check:
            zone = "Bommanahalli Region"
        else:
            zone = "EAST Region"

        ward = attrs.get("wardName") or "BBMP Ward"
        location = attrs.get("location") or "N/A"
        sim_provider = attrs.get("gsmProvider") or attrs.get("simName") or "Vi India"

        # Connectivity calculation (Prioritizing systime to match ThingsBoard dashboard)
        systime_val = attrs.get("systime")
        last_ms_val = attrs.get("lastActivityTime") or attrs.get("lastConnectTime")
        raw_active = attrs.get("active")
        now_sec = time.time()
        
        if systime_val:
            try:
                systime_sec = float(systime_val)
                diff_sec = max(0, now_sec - systime_sec)
                diff_hours = diff_sec / 3600.0
                offline_days = int(diff_sec / 86400.0)
                last_activity_str = datetime.fromtimestamp(systime_sec).strftime("%Y-%m-%d %H:%M:%S")
                is_active = (diff_hours <= 24)
            except Exception:
                diff_hours = 168
                offline_days = 7
                last_activity_str = "Unknown"
                is_active = False
        elif last_ms_val:
            try:
                last_ms_float = float(last_ms_val)
                diff_ms = max(0, now_ms - last_ms_float)
                diff_hours = diff_ms / (1000 * 3600)
                offline_days = int(diff_ms / (1000 * 3600 * 24))
                last_activity_str = datetime.fromtimestamp(last_ms_float / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                is_active = (diff_hours <= 24)
            except Exception:
                diff_hours = 168
                offline_days = 7
                last_activity_str = "Unknown"
                is_active = False
        else:
            is_active = (raw_active in (True, "true", "True") or dev.get("active", False))
            diff_hours = 0 if is_active else 168
            offline_days = 0 if is_active else 7
            last_activity_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Power failure (PF) detection adhering strictly to ThingsBoard ccmsOfflineFilter logic (pkt == 8)
        fault_code_val = str(attrs.get("faultCode") or "").strip()
        pkt_val = str(attrs.get("pkt") or "").strip()

        # Dynamic Power Failure (PF) detection matching ThingsBoard dashboard native filter
        is_pf = (pkt_val == "8") or ("pf" in fault_code_val.lower())

        status = "Online" if is_active else "Offline"
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

        # Electrical Telemetry values
        def parse_float(val, divisor=1.0):
            if val is None or val == "":
                return None
            try:
                return round(float(val) / divisor, 2)
            except Exception:
                return None

        # Voltage values in ThingsBoard are often in millivolts or volts
        rv = parse_float(attrs.get("rv"))
        yv = parse_float(attrs.get("yv"))
        bv = parse_float(attrs.get("bv"))
        if rv and rv > 1000: rv = round(rv / 1000, 1)
        if yv and yv > 1000: yv = round(yv / 1000, 1)
        if bv and bv > 1000: bv = round(bv / 1000, 1)

        record = {
            "device_id": dev_id,
            "meter_number": meter_id,
            "feeder_name": feeder_label,
            "device_type": device_type,
            "zone": zone,
            "ward": ward,
            "location": location,
            "sim_provider": sim_provider,
            "status": status,
            "is_active": is_active,
            "offline_days": offline_days,
            "hours_since_last_comm": round(diff_hours, 1),
            "last_activity_time": last_activity_str,
            "root_cause_tag": root_cause,
            "r_volt": rv,
            "y_volt": yv,
            "b_volt": bv,
            "r_current": parse_float(attrs.get("ri")),
            "y_current": parse_float(attrs.get("yi")),
            "b_current": parse_float(attrs.get("bi")),
            "total_kw": parse_float(attrs.get("tkw")),
            "cumulative_kwh": parse_float(attrs.get("kwh")),
            "freq_hz": parse_float(attrs.get("freq")),
            "rssi_signal": parse_float(attrs.get("rssi")),
            "is_pf": is_pf,
            "customer": "Bangalore (BBMP)"
        }
        panels_data.append(record)

    # 5. Export to JSON & CSV
    logger.info(f"Saving {len(panels_data)} records to {output_json}...")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(panels_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saving summary CSV to {output_csv}...")
    fieldnames = [
        "meter_number", "feeder_name", "zone", "ward", "status", "offline_days",
        "last_activity_time", "root_cause_tag", "r_volt", "y_volt", "b_volt",
        "total_kw", "cumulative_kwh", "sim_provider", "location", "device_id"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(panels_data)

    # 6. Generate Analytics Summary
    online_count = sum(1 for p in panels_data if p["is_active"])
    offline_count = total_devices - online_count
    chronic_all = sum(1 for p in panels_data if not p["is_active"] and p["offline_days"] >= 7)
    pf_count = sum(1 for p in panels_data if p.get("is_pf", False) and not p["is_active"] and p["offline_days"] >= 7)
    chronic_offline_count = chronic_all - pf_count  # Excludes PF panels

    zone_counts = Counter(p["zone"] for p in panels_data)
    zone_offline = Counter(p["zone"] for p in panels_data if not p["is_active"] and not p.get("is_pf", False))
    sim_counts = Counter(p["sim_provider"] for p in panels_data)

    print("\n" + "="*75)
    print("  SCHNELL IoT - BANGALORE (BBMP) REAL-TIME DATA SUMMARY")
    print("="*75)
    print(f"  * Total Monitored Panels      : {total_devices}")
    print(f"  * Online Panels               : {online_count} ({online_count/total_devices*100:.1f}%)")
    print(f"  * Offline Panels              : {offline_count} ({offline_count/total_devices*100:.1f}%)")
    print(f"  * Total Panels Inactive >7D   : {chronic_all} panels")
    print(f"  * Power Failure (PF) Inactive : {pf_count} panels (Utility grid power cut / BESCOM)")
    print(f"  * Chronic Comms Offline (>7D) : {chronic_offline_count} panels (EXCLUDING PF PANELS)")

    print("\n  ZONE BREAKDOWN:")
    print(f"  {'Zone':<20} | {'Total':<8} | {'Online':<8} | {'Offline':<8} | {'Online %':<8}")
    print("  " + "-"*60)
    for z, tot in zone_counts.most_common():
        off = zone_offline.get(z, 0)
        on = tot - off
        pct = (on / tot * 100) if tot else 0
        print(f"  {z:<20} | {tot:<8} | {on:<8} | {off:<8} | {pct:>6.1f}%")

    print("\n  CELLULAR CARRIERS / SIM PROVIDERS:")
    for sim, c in sim_counts.most_common():
        print(f"  * {sim:<20}: {c} panels ({c/total_devices*100:.1f}%)")

    print("\n  SAMPLE REAL-TIME ONLINE PANEL:")
    online_samples = [p for p in panels_data if p["is_active"] and p.get("r_volt")]
    if online_samples:
        s = online_samples[0]
        print(f"    - Meter / Feeder : {s['meter_number']} / {s['feeder_name']}")
        print(f"    - Zone & Ward    : {s['zone']} ({s['ward']})")
        print(f"    - Last Comm      : {s['last_activity_time']} ({s['hours_since_last_comm']}h ago)")
        print(f"    - Phase Voltages : R={s['r_volt']}V, Y={s['y_volt']}V, B={s['b_volt']}V")
        print(f"    - Total kW / kWh : {s['total_kw']} kW | {s['cumulative_kwh']} kWh")
        print(f"    - SIM / Signal   : {s['sim_provider']} (RSSI: {s['rssi_signal']})")
        print(f"    - Location       : {s['location']}")

    print("\n  SAMPLE CHRONIC OFFLINE PANEL (>7 DAYS):")
    chronic_samples = [p for p in panels_data if not p["is_active"] and p["offline_days"] >= 7]
    if chronic_samples:
        s = chronic_samples[0]
        print(f"    - Meter / Feeder : {s['meter_number']} / {s['feeder_name']}")
        print(f"    - Zone & Ward    : {s['zone']} ({s['ward']})")
        print(f"    - Inactivity     : {s['offline_days']} Days ({s['last_activity_time']})")
        print(f"    - Root Cause     : {s['root_cause_tag']}")
        print(f"    - Location       : {s['location']}")

    print("\n" + "="*75)
    print(f"  SUCCESS: Exported full BBMP dataset to:")
    print(f"  -> JSON: {os.path.abspath(output_json)}")
    print(f"  -> CSV : {os.path.abspath(output_csv)}")
    print("="*75 + "\n")

    return panels_data

if __name__ == "__main__":
    fetch_schnell_bbmp_data()
