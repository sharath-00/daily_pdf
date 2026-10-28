"""
Script to fetch real-time Grievance and Maintenance Tickets from Firebase Firestore for Bangalore (BBMP) Project.
Fetches all ticket categories: Sahaya / Public Complaints, Municipal Officials, O&M Internal, and Auto CMS Alerts.
Saves data to JSON and CSV files and prints an executive summary.
"""
import os
import json
import csv
import logging
from datetime import datetime
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BBMPTicketFetcher")

def parse_firestore_field(v):
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
        return [parse_firestore_field(x) for x in v.get("arrayValue", {}).get("values", [])]
    if "mapValue" in v:
        return {k: parse_firestore_field(val) for k, val in v.get("mapValue", {}).get("fields", {}).items()}
    for val in v.values():
        return val
    return None

def parse_datetime(val):
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

def fetch_bbmp_tickets(output_json="bbmp_tickets_data.json", output_csv="bbmp_tickets_summary.csv"):
    project_id = Config.FIREBASE_PROJECT_ID
    database_id = Config.FIREBASE_DATABASE_ID
    collection_id = Config.FIREBASE_COLLECTION_ID
    customer_id = Config.BBMP_CUSTOMER_ID
    target_customer = Config.TARGET_CUSTOMER

    print("\n" + "="*75)
    print("  FIREBASE FIRESTORE - BANGALORE (BBMP) TICKETS INGESTION")
    print(f"  Project ID   : {project_id}")
    print(f"  Database ID  : {database_id}")
    print(f"  Collection   : {collection_id}")
    print(f"  Customer ID  : {customer_id} ({target_customer})")
    print("="*75 + "\n")

    url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database_id}/documents:runQuery"
    session = requests.Session()

    # Query partitions to ensure full coverage across all complaint channels
    categories = [
        ("Public", 1500),         # BBMP Sahaya citizen complaints
        ("Officials", 1000),      # Municipal corporators & BBMP ward engineers
        ("O&M (CMS)", 2000),      # Internal contractor O&M field tasks
        ("Auto", 2500)            # Automated CCMS hardware alarms
    ]

    all_raw_docs = {}

    def fetch_partition(comp, limit):
        logger.info(f"Querying Firestore partition '{comp}' (limit {limit})...")
        payload = {
            "structuredQuery": {
                "from": [{"collectionId": collection_id}],
                "where": {
                    "compositeFilter": {
                        "op": "AND",
                        "filters": [
                            {
                                "fieldFilter": {
                                    "field": {"fieldPath": "customer_id"},
                                    "op": "EQUAL",
                                    "value": {"stringValue": customer_id}
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
            r = session.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                for item in r.json():
                    if "document" in item:
                        res.append(item["document"])
                logger.info(f"  -> Partition '{comp}': Ingested {len(res)} documents.")
            else:
                logger.warning(f"  -> Partition '{comp}' returned HTTP {r.status_code}: {r.text[:150]}")
        except Exception as ex:
            logger.error(f"  -> Exception in partition '{comp}': {ex}")
        return res

    # Also query the most recent tickets created (ordered by ticket_opened_on DESC)
    def fetch_recent_tickets(limit=1500):
        logger.info(f"Querying most recent real-time tickets (ordered by date DESC, limit {limit})...")
        payload = {
            "structuredQuery": {
                "from": [{"collectionId": collection_id}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "customer_id"},
                        "op": "EQUAL",
                        "value": {"stringValue": customer_id}
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
            r = session.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                for item in r.json():
                    if "document" in item:
                        res.append(item["document"])
                logger.info(f"  -> Recent tickets query: Ingested {len(res)} documents.")
            else:
                logger.warning(f"  -> Recent query returned HTTP {r.status_code}")
        except Exception as ex:
            logger.error(f"  -> Exception in recent tickets query: {ex}")
        return res

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_partition, c[0], c[1]): c[0] for c in categories}
        futures[executor.submit(fetch_recent_tickets, 1500)] = "Recent"

        for fut in as_completed(futures):
            docs = fut.result()
            for d in docs:
                doc_name = d.get("name", "")
                if doc_name:
                    all_raw_docs[doc_name] = d

    logger.info(f"Total unique Firestore documents retrieved: {len(all_raw_docs)}")

    # Standardize records
    now_dt = datetime.now()
    tickets_data = []

    for doc_name, doc in all_raw_docs.items():
        doc_id = doc_name.split("/")[-1]
        fields = doc.get("fields", {})
        data = {k: parse_firestore_field(v) for k, v in fields.items()}

        ticket_id = data.get("ticket_id") or data.get("complaint_no") or doc_id
        complainee_raw = str(data.get("complainee", "")).strip()

        # Categorize Channel / Source
        if complainee_raw.lower() in ("officials", "official"):
            source = "Sahaya App (Officials)"  # Official tickets are the BBMP Sahaya app complaints
        elif complainee_raw.lower() in ("public", "citizen"):
            source = "Citizen Grievance Portal"
        elif "o&m" in complainee_raw.lower() or "serviceman" in complainee_raw.lower() or "field" in complainee_raw.lower():
            source = "Field App / Internal"
        elif "auto" in complainee_raw.lower() or "system" in complainee_raw.lower():
            source = "Auto CMS Alert"
        else:
            source = complainee_raw or "Portal"

        # Status & Resolution
        status = str(data.get("status", "Open")).strip()
        status_lower = status.lower()
        is_resolved = ("close" in status_lower or status_lower in ("resolved", "completed", "done", "fixed", "visited-closed", "verified-closed"))

        # Timestamps & Aging
        opened_str = data.get("ticket_opened_on") or data.get("created_at") or data.get("date")
        closed_str = data.get("ticket_closed_on") or data.get("resolved_at") or data.get("closed_at") or data.get("last_updated_on")

        opened_dt = parse_datetime(opened_str) or now_dt
        closed_dt = parse_datetime(closed_str) if is_resolved else None

        if is_resolved and closed_dt:
            aging_days = max(0, (closed_dt - opened_dt).days)
        else:
            aging_days = max(0, (now_dt - opened_dt).days)

        zone = data.get("zone") or data.get("region") or "Bangalore Zone"
        if not zone or zone.strip() == "":
            zone = "Bangalore Zone"
        if zone.lower() == "bommanahali":
            zone = "Bommanahalli"

        ward = data.get("ward") or "BBMP Ward"
        if not ward or ward.strip() == "":
            ward = "BBMP Ward"

        problem_type = data.get("problem_type") or data.get("issue_category") or data.get("issue_identified") or data.get("description") or "Streetlight issue"
        location = data.get("location") or data.get("user_location") or "N/A"
        assignee = data.get("assignee") or data.get("assigned_to") or "Unassigned"
        if not assignee or assignee.strip() == "":
            assignee = "Unassigned"

        opened_by = data.get("ticket_opened_by") or "System"
        contact_no = str(data.get("complainee_contact_no") or "")
        if contact_no and len(contact_no) > 4:
            contact_masked = contact_no[:4] + "****" + contact_no[-2:]
        else:
            contact_masked = "N/A"

        record = {
            "ticket_id": ticket_id,
            "source": source,
            "complainee": complainee_raw or "Auto",
            "status": status,
            "is_resolved": is_resolved,
            "problem_type": str(problem_type)[:70],
            "zone": zone,
            "ward": ward,
            "location": str(location).replace("\n", " ")[:120],
            "ticket_opened_on": opened_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "ticket_closed_on": closed_dt.strftime("%Y-%m-%d %H:%M:%S") if closed_dt else "Pending",
            "aging_days": aging_days,
            "assigned_to": assignee,
            "ticket_opened_by": opened_by,
            "complainee_contact": contact_masked,
            "sla_breached": (aging_days > 3 and not is_resolved),
            "customer": target_customer,
            "doc_id": doc_id
        }
        tickets_data.append(record)

    # Sort tickets by opened_on descending
    tickets_data.sort(key=lambda x: x["ticket_opened_on"], reverse=True)

    # Export to JSON & CSV
    logger.info(f"Saving {len(tickets_data)} tickets to {output_json}...")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(tickets_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saving tickets summary to {output_csv}...")
    fieldnames = [
        "ticket_id", "source", "complainee", "status", "is_resolved",
        "problem_type", "zone", "ward", "location", "ticket_opened_on",
        "ticket_closed_on", "aging_days", "assigned_to", "sla_breached"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tickets_data)

    # Analytics Summary
    total_tix = len(tickets_data)
    resolved_tix = sum(1 for t in tickets_data if t["is_resolved"])
    pending_tix = total_tix - resolved_tix
    res_rate = (resolved_tix / total_tix * 100) if total_tix else 0

    status_counts = Counter(t["status"] for t in tickets_data)
    source_groups = defaultdict(list)
    for t in tickets_data:
        source_groups[t["source"]].append(t)

    zone_pending = Counter(t["zone"] for t in tickets_data if not t["is_resolved"])
    problem_counts = Counter(t["problem_type"] for t in tickets_data)

    # Sahaya Metrics
    sahaya_list = source_groups.get("Sahaya", [])
    sahaya_tot = len(sahaya_list)
    sahaya_res = sum(1 for t in sahaya_list if t["is_resolved"])
    sahaya_pen = sahaya_tot - sahaya_res
    sahaya_pct = (sahaya_res / sahaya_tot * 100) if sahaya_tot else 0
    sahaya_tats = [t["aging_days"] for t in sahaya_list if t["is_resolved"]]
    sahaya_avg_tat = (sum(sahaya_tats) / len(sahaya_tats)) if sahaya_tats else 0

    print("\n" + "="*75)
    print("  FIREBASE FIRESTORE - BANGALORE (BBMP) TICKETS SUMMARY")
    print("="*75)
    print(f"  * Total Tickets Ingested   : {total_tix}")
    print(f"  * Resolved Tickets         : {resolved_tix} ({res_rate:.1f}%)")
    print(f"  * Pending / Open Tickets   : {pending_tix} ({(pending_tix/total_tix*100):.1f}%)")
    print(f"  * Critical Overdue (>7D)   : {sum(1 for t in tickets_data if not t['is_resolved'] and t['aging_days'] >= 7)} tickets")

    print("\n  CHANNEL / SOURCE PERFORMANCE BREAKDOWN:")
    print(f"  {'Channel / Source':<26} | {'Total':<7} | {'Resolved':<8} | {'Pending':<8} | {'Res %':<7} | {'Avg TAT':<8}")
    print("  " + "-"*72)
    for src, t_list in sorted(source_groups.items(), key=lambda x: len(x[1]), reverse=True):
        s_tot = len(t_list)
        s_res = sum(1 for t in t_list if t["is_resolved"])
        s_pen = s_tot - s_res
        s_pct = (s_res / s_tot * 100) if s_tot else 0
        s_tats = [t["aging_days"] for t in t_list if t["is_resolved"]]
        s_tat = (sum(s_tats) / len(s_tats)) if s_tats else 0
        tag = " [CITIZEN]" if src == "Sahaya" else ""
        print(f"  {src + tag:<26} | {s_tot:<7} | {s_res:<8} | {s_pen:<8} | {s_pct:>5.1f}% | {s_tat:>4.1f} d")

    print("\n  STATUS BREAKDOWN:")
    for st, c in status_counts.most_common():
        print(f"  * {st:<18}: {c} ({(c/total_tix*100):.1f}%)")

    print("\n  TOP 5 PROBLEM TYPES / FAULT CATEGORIES:")
    for prob, c in problem_counts.most_common(5):
        print(f"  * {prob:<35}: {c} tickets")

    print("\n  TOP ZONES BY PENDING COMPLAINTS:")
    for z, c in zone_pending.most_common(6):
        print(f"  * {z:<25}: {c} pending tickets")

    print("\n  SAMPLE REAL-TIME CITIZEN (SAHAYA) COMPLAINTS:")
    sahaya_samples = [t for t in sahaya_list if not t["is_resolved"]]
    if not sahaya_samples:
        sahaya_samples = sahaya_list[:2]
    for s in sahaya_samples[:3]:
        print(f"    - Ticket ID : {s['ticket_id']} | Status: {s['status']} | Aging: {s['aging_days']} days")
        print(f"      Issue     : {s['problem_type']}")
        print(f"      Zone/Ward : {s['zone']} ({s['ward']})")
        print(f"      Location  : {s['location']}")
        print(f"      Opened On : {s['ticket_opened_on']} (Contact: {s['complainee_contact']})")

    print("\n  SAMPLE CRITICAL CHRONIC OVERDUE TICKETS (>14 DAYS):")
    chronic_samples = [t for t in tickets_data if not t["is_resolved"] and t["aging_days"] >= 14]
    for s in chronic_samples[:3]:
        print(f"    - Ticket ID : {s['ticket_id']} ({s['source']}) | Pending: {s['aging_days']} days | Assigned: {s['assigned_to']}")
        print(f"      Issue     : {s['problem_type']}")
        print(f"      Zone/Ward : {s['zone']} ({s['ward']})")
        print(f"      Opened On : {s['ticket_opened_on']}")

    print("\n" + "="*75)
    print(f"  SUCCESS: Exported BBMP tickets dataset to:")
    print(f"  -> JSON: {os.path.abspath(output_json)}")
    print(f"  -> CSV : {os.path.abspath(output_csv)}")
    print("="*75 + "\n")

    return tickets_data

if __name__ == "__main__":
    fetch_bbmp_tickets()
