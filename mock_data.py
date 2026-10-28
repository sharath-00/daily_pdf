"""
Generates realistic mock telemetry and ticket data for Bangalore (BBMP) Smart Lighting.
Used for testing and when live API credentials are being configured.
"""
from datetime import datetime, timedelta
import random

def get_mock_telemetry_data(offline_threshold_days=7):
    """
    Returns simulated ThingsBoard panel telemetry.
    """
    now = datetime.now()
    zones = ["Mahadevapura", "Bommanahalli", "Bangalore South", "Bangalore East", "Bangalore West", "RR Nagar", "Dasarahalli", "Yelahanka"]
    panels = []
    
    # Generate 120 total panels
    # ~75 online (communicated within last few hours)
    # ~15 offline 1-6 days
    # ~30 offline > 7 days (chronic offline panels)
    
    # 1. Chronic offline panels (> 7 days)
    chronic_durations = [38, 29, 24, 21, 19, 17, 16, 14, 13, 12, 11, 10, 9, 8, 8, 31, 25, 22, 18, 15, 14, 12, 10, 9, 8, 42, 35, 27, 20, 16]
    root_causes = [
        "BESCOM Power Outage / Feeder Cut",
        "MCB Trip - Phase Disconnect",
        "Modem / 4G SIM Communication Failure",
        "Road Widening / Cable Snag",
        "Transformer Maintenance",
        "Underground Cable Damage"
    ]
    
    for i, days in enumerate(chronic_durations):
        zone = zones[i % len(zones)]
        ward_no = 50 + (i * 3) % 148
        last_seen = now - timedelta(days=days, hours=random.randint(1, 23))
        panel_id = f"BBMP-{zone[:3].upper()}-PNL-{100 + i}"
        panels.append({
            "panel_id": panel_id,
            "panel_name": f"{zone} Ward {ward_no} CCMS-{100 + i}",
            "zone": zone,
            "ward": f"Ward {ward_no}",
            "is_active": False,
            "status": "Offline",
            "last_activity_time": last_seen.strftime("%Y-%m-%d %H:%M"),
            "offline_days": days,
            "root_cause_tag": random.choice(root_causes),
            "customer": "Bangalore (BBMP)"
        })
        
    # 2. Recently offline panels (1 to 6 days)
    for i in range(15):
        days = random.randint(1, 6)
        zone = random.choice(zones)
        last_seen = now - timedelta(days=days, hours=random.randint(1, 23))
        panel_id = f"BBMP-{zone[:3].upper()}-PNL-{200 + i}"
        panels.append({
            "panel_id": panel_id,
            "panel_name": f"{zone} CCMS-{200 + i}",
            "zone": zone,
            "ward": f"Ward {random.randint(1, 198)}",
            "is_active": False,
            "status": "Offline",
            "last_activity_time": last_seen.strftime("%Y-%m-%d %H:%M"),
            "offline_days": days,
            "root_cause_tag": "Network Intermittent / Inspection Pending",
            "customer": "Bangalore (BBMP)"
        })
        
    # 3. Online panels
    for i in range(75):
        zone = random.choice(zones)
        last_seen = now - timedelta(minutes=random.randint(5, 180))
        panel_id = f"BBMP-{zone[:3].upper()}-PNL-{300 + i}"
        panels.append({
            "panel_id": panel_id,
            "panel_name": f"{zone} CCMS-{300 + i}",
            "zone": zone,
            "ward": f"Ward {random.randint(1, 198)}",
            "is_active": True,
            "status": "Online",
            "last_activity_time": last_seen.strftime("%Y-%m-%d %H:%M"),
            "offline_days": 0,
            "root_cause_tag": "Normal Operation",
            "customer": "Bangalore (BBMP)"
        })
        
    return panels


def get_mock_tickets_data():
    """
    Returns simulated Firebase ticket documents for Bangalore (BBMP).
    Demonstrates Sahaya complaints with high resolution rate and specific chronic unresolved tickets.
    """
    now = datetime.now()
    zones = ["Mahadevapura", "Bommanahalli", "Bangalore South", "Bangalore East", "Bangalore West", "RR Nagar", "Dasarahalli", "Yelahanka"]
    tickets = []
    
    # 1. Sahaya Complaints: 52 total tickets, 46 resolved (Resolution rate = ~88.5% -> High!)
    for i in range(1, 53):
        is_resolved = i <= 46
        zone = zones[i % len(zones)]
        created_days_ago = random.randint(2, 30) if is_resolved else random.randint(1, 24)
        created_at = now - timedelta(days=created_days_ago, hours=random.randint(1, 12))
        
        ticket_id = f"SHY-BBMP-{8000 + i}"
        
        if is_resolved:
            resolved_days_ago = max(0, created_days_ago - random.randint(1, 4))
            resolved_at = now - timedelta(days=resolved_days_ago)
            aging_days = (resolved_at - created_at).days
            status = "Resolved"
        else:
            resolved_at = None
            aging_days = (now - created_at).days
            status = "In Progress" if aging_days < 7 else "Open (Escalated)"
            
        issue_categories = [
            "Streetlight flickering / dim",
            "Complete phase dark / unlit stretch",
            "Pole leaning / damaged by vehicle",
            "Timer out of sync / glowing in daytime",
            "Broken luminaires",
            "Earthing fault"
        ]
        
        tickets.append({
            "ticket_id": ticket_id,
            "source": "Sahaya",
            "customer": "Bangalore (BBMP)",
            "zone": zone,
            "ward": f"Ward {random.randint(1, 198)}",
            "issue_category": random.choice(issue_categories),
            "status": status,
            "is_resolved": is_resolved,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M"),
            "resolved_at": resolved_at.strftime("%Y-%m-%d %H:%M") if resolved_at else None,
            "aging_days": aging_days,
            "assigned_to": f"Zone Engineer {zone[:4]}",
            "sla_breached": aging_days > 3 and not is_resolved
        })
        
    # Introduce explicit chronic unresolved Sahaya tickets (specifically requested by user)
    # E.g., Ticket SHY-BBMP-8049 unresolved for 23 days in Mahadevapura
    chronic_tickets = [
        {
            "ticket_id": "SHY-BBMP-8049",
            "source": "Sahaya",
            "customer": "Bangalore (BBMP)",
            "zone": "Mahadevapura",
            "ward": "Ward 85 (Doddanekkundi)",
            "issue_category": "Underground cable snapped by water pipeline trenching",
            "status": "Pending Spare / Civil Clearance",
            "is_resolved": False,
            "created_at": (now - timedelta(days=23)).strftime("%Y-%m-%d %H:%M"),
            "resolved_at": None,
            "aging_days": 23,
            "assigned_to": "Field Sup. Ramesh K.",
            "sla_breached": True,
            "escalation_note": "Awaiting BWSSB trench clearance; 14 streetlights dark"
        },
        {
            "ticket_id": "SHY-BBMP-8051",
            "source": "Sahaya",
            "customer": "Bangalore (BBMP)",
            "zone": "Bommanahalli",
            "ward": "Ward 174 (HSR Layout)",
            "issue_category": "Phase failure on 11kV BESCOM feed to CCMS panel",
            "status": "Escalated to BESCOM",
            "is_resolved": False,
            "created_at": (now - timedelta(days=16)).strftime("%Y-%m-%d %H:%M"),
            "resolved_at": None,
            "aging_days": 16,
            "assigned_to": "BESCOM Liaison Suresh",
            "sla_breached": True,
            "escalation_note": "Repeated citizen escalation on Sahaya portal; pending transformer tap fix"
        },
        {
            "ticket_id": "INT-BBMP-3410",
            "source": "Field App / Internal",
            "customer": "Bangalore (BBMP)",
            "zone": "Bangalore West",
            "ward": "Ward 134 (Bapuji Nagar)",
            "issue_category": "Damaged control box & burnt contactor",
            "status": "Material Indented",
            "is_resolved": False,
            "created_at": (now - timedelta(days=18)).strftime("%Y-%m-%d %H:%M"),
            "resolved_at": None,
            "aging_days": 18,
            "assigned_to": "Tech Team Lead Manoj",
            "sla_breached": True,
            "escalation_note": "Replacement contactor module requisition pending approval"
        }
    ]
    tickets.extend(chronic_tickets)
    
    # 2. Other Tickets (Citizen Helpline & Internal Field App): 40 tickets, ~26 resolved (~65% resolution rate)
    for i in range(1, 41):
        is_resolved = i <= 26
        zone = zones[i % len(zones)]
        source = "Control Room / Helpline" if i % 2 == 0 else "Field App / Internal"
        created_days_ago = random.randint(2, 25)
        created_at = now - timedelta(days=created_days_ago, hours=random.randint(1, 12))
        
        ticket_id = f"HLP-BBMP-{5000 + i}" if "Helpline" in source else f"FLD-BBMP-{6000 + i}"
        
        if is_resolved:
            resolved_days_ago = max(0, created_days_ago - random.randint(1, 5))
            resolved_at = now - timedelta(days=resolved_days_ago)
            aging_days = (resolved_at - created_at).days
            status = "Closed"
        else:
            resolved_at = None
            aging_days = (now - created_at).days
            status = "Work In Progress" if aging_days < 7 else "Pending Material"
            
        tickets.append({
            "ticket_id": ticket_id,
            "source": source,
            "customer": "Bangalore (BBMP)",
            "zone": zone,
            "ward": f"Ward {random.randint(1, 198)}",
            "issue_category": "Luminaire failure or pole rewiring",
            "status": status,
            "is_resolved": is_resolved,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M"),
            "resolved_at": resolved_at.strftime("%Y-%m-%d %H:%M") if resolved_at else None,
            "aging_days": aging_days,
            "assigned_to": f"Field Tech {zone[:3]}",
            "sla_breached": aging_days > 4 and not is_resolved
        })
        
    return tickets
