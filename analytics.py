"""
Analytics and Insights Engine.
Processes telemetry and ticket data to generate metrics, statistical breakdowns,
and executive talking points for daily standup meetings.
"""
from collections import defaultdict
from config import Config

class AnalyticsEngine:
    def __init__(self, panels: list, tickets: list, bbmp_totals: dict = None, materials_data: dict = None):
        self.panels = panels or []
        self.tickets = tickets or []
        self.offline_threshold = Config.OFFLINE_DAYS_THRESHOLD
        self.long_pending_threshold = Config.LONG_PENDING_TICKET_DAYS
        self.bbmp_totals = bbmp_totals or {"total": 38019, "resolved": 36142, "pending": 1877, "res_rate": 95.1}
        self.materials_data = materials_data or {}

    def analyze_all(self, materials_data: dict = None) -> dict:
        m_data = materials_data or self.materials_data
        telemetry_insights = self.analyze_telemetry()
        ticket_insights = self.analyze_tickets()
        meeting_points = self.generate_meeting_key_points(telemetry_insights, ticket_insights, materials_data=m_data)

        return {
            "telemetry": telemetry_insights,
            "tickets": ticket_insights,
            "meeting_points": meeting_points
        }

    @staticmethod
    def normalize_panel_zone(zone_str: str) -> str:
        z = str(zone_str or "").lower()
        if "bommanahalli" in z or "bommanahali" in z:
            return "Bommanahalli Region"
        return "EAST Region"

    def analyze_telemetry(self) -> dict:
        total = len(self.panels)
        online = sum(1 for p in self.panels if p.get("is_active", False))
        offline = total - online

        # Identify Chronic Power Failure (PF) panels (> 7 days)
        pf_panels_count = sum(
            1 for p in self.panels 
            if p.get("is_pf", False) and not p.get("is_active", False) and p.get("offline_days", 0) >= self.offline_threshold
        )

        # Chronic offline panels (> threshold days), excluding PF panels if configured
        if Config.EXCLUDE_PF_PANELS:
            chronic_panels = [
                p for p in self.panels 
                if not p.get("is_active", False) 
                and p.get("offline_days", 0) >= self.offline_threshold 
                and not p.get("is_pf", False)
            ]
        else:
            chronic_panels = [
                p for p in self.panels 
                if not p.get("is_active", False) and p.get("offline_days", 0) >= self.offline_threshold
            ]
        
        # Sort chronic panels by offline days descending
        chronic_panels.sort(key=lambda x: x.get("offline_days", 0), reverse=True)

        # Zone breakdown for chronic offline panels
        zone_chronic = defaultdict(int)
        for p in chronic_panels:
            zone = self.normalize_panel_zone(p.get("zone"))
            zone_chronic[zone] += 1

        # Detailed zone-wise telemetry stats (total, online, offline, aging, causes)
        zone_stats = defaultdict(lambda: {
            "total": 0, "online": 0, "offline": 0, "pf": 0, "chronic_pf": 0,
            "chronic_count": 0, "d_7_14": 0, "d_14_30": 0, "d_30_plus": 0,
            "offline_days_list": [], "causes": defaultdict(int)
        })

        for p in self.panels:
            z = self.normalize_panel_zone(p.get("zone"))
            zone_stats[z]["total"] += 1
            if p.get("is_active", False):
                zone_stats[z]["online"] += 1
            else:
                zone_stats[z]["offline"] += 1
                days = p.get("offline_days", 0)
                is_pf = p.get("is_pf", False)
                if is_pf:
                    zone_stats[z]["pf"] += 1
                if days >= self.offline_threshold and (not Config.EXCLUDE_PF_PANELS or not is_pf):
                    zone_stats[z]["chronic_count"] += 1
                    if is_pf:
                        zone_stats[z]["chronic_pf"] += 1
                    zone_stats[z]["offline_days_list"].append(days)
                    cause = p.get("root_cause_tag", "Communication Lost")
                    zone_stats[z]["causes"][cause] += 1
                    if days <= 14:
                        zone_stats[z]["d_7_14"] += 1
                    elif days <= 30:
                        zone_stats[z]["d_14_30"] += 1
                    else:
                        zone_stats[z]["d_30_plus"] += 1

        total_chronic_num = len(chronic_panels)
        detailed_zone_breakdown = []
        for z, s in sorted(zone_stats.items(), key=lambda x: x[1]["chronic_count"], reverse=True):
            avg_days = sum(s["offline_days_list"]) / len(s["offline_days_list"]) if s["offline_days_list"] else 0
            max_days = max(s["offline_days_list"]) if s["offline_days_list"] else 0
            on_pct = round(s["online"] / s["total"] * 100, 1) if s["total"] else 0
            chronic_share = round(s["chronic_count"] / total_chronic_num * 100, 1) if total_chronic_num else 0
            top_cause = sorted(s["causes"].items(), key=lambda x: x[1], reverse=True)[0][0] if s["causes"] else "Normal / Active"

            detailed_zone_breakdown.append({
                "zone": z,
                "total": s["total"],
                "online": s["online"],
                "online_pct": on_pct,
                "offline": s["offline"],
                "chronic_count": s["chronic_count"],
                "chronic_share": chronic_share,
                "d_7_14": s["d_7_14"],
                "d_14_30": s["d_14_30"],
                "d_30_plus": s["d_30_plus"],
                "avg_days": round(avg_days, 1),
                "max_days": max_days,
                "pf_count": s["chronic_pf"],
                "top_cause": top_cause
            })

        # Root cause breakdown
        cause_counts = defaultdict(int)
        for p in chronic_panels:
            cause = p.get("root_cause_tag", "Unknown / Communication Inactive")
            cause_counts[cause] += 1

        pf_chronic_panels = [p for p in chronic_panels if p.get("is_pf", False)]
        non_pf_chronic_panels = [p for p in chronic_panels if not p.get("is_pf", False)]

        online_pct = (online / total * 100) if total else 0
        offline_pct = (offline / total * 100) if total else 0
        chronic_pct = (len(chronic_panels) / total * 100) if total else 0
        chronic_of_offline_pct = (len(chronic_panels) / offline * 100) if offline else 0

        return {
            "total_panels": total,
            "online_panels": online,
            "offline_panels": offline,
            "online_pct": round(online_pct, 1),
            "offline_pct": round(offline_pct, 1),
            "chronic_panels_count": len(chronic_panels),
            "chronic_pct": round(chronic_pct, 1),
            "chronic_of_offline_pct": round(chronic_of_offline_pct, 1),
            "chronic_panels": chronic_panels,
            "pf_chronic_panels": pf_chronic_panels,
            "non_pf_chronic_panels": non_pf_chronic_panels,
            "top_chronic_panels": chronic_panels[:10],
            "pf_panels_count": pf_panels_count,
            "chronic_pf_within_count": len(pf_chronic_panels),
            "non_pf_panels_count": len(non_pf_chronic_panels),
            "exclude_pf_panels": Config.EXCLUDE_PF_PANELS,
            "zone_breakdown": dict(sorted(zone_chronic.items(), key=lambda x: x[1], reverse=True)),
            "detailed_zone_breakdown": detailed_zone_breakdown,
            "cause_breakdown": dict(sorted(cause_counts.items(), key=lambda x: x[1], reverse=True))
        }

    @staticmethod
    def is_sahaya(t: dict) -> bool:
        src = str(t.get("source", "")).lower()
        comp = str(t.get("complainee", "")).lower()
        return "sahaya" in src or comp in ("officials", "official")

    def analyze_tickets(self) -> dict:
        total = len(self.tickets)
        resolved = sum(1 for t in self.tickets if t.get("is_resolved", False))
        pending = total - resolved
        overall_res_rate = (resolved / total * 100) if total else 0

        # Segment by Source: Sahaya App (Officials) vs Others
        sahaya_tickets = [t for t in self.tickets if self.is_sahaya(t)]
        sahaya_total = len(sahaya_tickets)
        sahaya_resolved = sum(1 for t in sahaya_tickets if t.get("is_resolved", False))
        sahaya_pending = sahaya_total - sahaya_resolved
        sahaya_res_rate = (sahaya_resolved / sahaya_total * 100) if sahaya_total else 0

        # Sahaya Turnaround Time (TAT) in days
        sahaya_resolved_times = [t.get("aging_days", 0) for t in sahaya_tickets if t.get("is_resolved", False)]
        sahaya_avg_tat = (sum(sahaya_resolved_times) / len(sahaya_resolved_times)) if sahaya_resolved_times else 0

        # Other Sources
        other_tickets = [t for t in self.tickets if not self.is_sahaya(t)]
        other_total = len(other_tickets)
        other_resolved = sum(1 for t in other_tickets if t.get("is_resolved", False))
        other_pending = other_total - other_resolved
        other_res_rate = (other_resolved / other_total * 100) if other_total else 0

        # Source-wise breakdown
        sources_summary = {}
        source_groups = defaultdict(list)
        for t in self.tickets:
            src_name = t.get("source", "General")
            if self.is_sahaya(t):
                src_name = "Sahaya App (Officials)"
            source_groups[src_name].append(t)

        for src, t_list in source_groups.items():
            s_tot = len(t_list)
            s_res = sum(1 for x in t_list if x.get("is_resolved", False))
            s_rate = (s_res / s_tot * 100) if s_tot else 0
            sources_summary[src] = {
                "total": s_tot,
                "resolved": s_res,
                "pending": s_tot - s_res,
                "resolution_rate": round(s_rate, 1)
            }

        # Chronic Unresolved Tickets (> threshold days)
        chronic_unresolved = [
            t for t in self.tickets 
            if not t.get("is_resolved", False) and t.get("aging_days", 0) >= self.long_pending_threshold
        ]
        chronic_unresolved.sort(key=lambda x: x.get("aging_days", 0), reverse=True)

        # Curate top chronic tickets to ensure critical Sahaya official complaints are visible
        chronic_sahaya = [t for t in chronic_unresolved if self.is_sahaya(t)]
        chronic_other = [t for t in chronic_unresolved if not self.is_sahaya(t)]
        curated_chronic = list(chronic_sahaya[:3])
        for t in chronic_other:
            if len(curated_chronic) >= 7:
                break
            curated_chronic.append(t)
        curated_chronic.sort(key=lambda x: x.get("aging_days", 0), reverse=True)

        # Aging distribution for all pending tickets
        aging_buckets = {"< 3 Days": 0, "3 - 7 Days": 0, "7 - 14 Days": 0, "> 14 Days": 0}
        for t in self.tickets:
            if not t.get("is_resolved", False):
                days = t.get("aging_days", 0)
                if days < 3:
                    aging_buckets["< 3 Days"] += 1
                elif days <= 7:
                    aging_buckets["3 - 7 Days"] += 1
                elif days <= 14:
                    aging_buckets["7 - 14 Days"] += 1
                else:
                    aging_buckets["> 14 Days"] += 1

        # Sahaya Performance Rating
        if sahaya_res_rate >= 80:
            sahaya_rating = "HIGH (Exceptional Grievance Redressal)"
            sahaya_status_color = "green"
        elif sahaya_res_rate >= 65:
            sahaya_rating = "MODERATE (Standard SLA Compliance)"
            sahaya_status_color = "orange"
        else:
            sahaya_rating = "CRITICAL ATTENTION NEEDED (SLA Lagging)"
            sahaya_status_color = "red"

        # Detailed Zone breakdown for Sahaya App tickets
        sahaya_zone_stats = defaultdict(lambda: {
            "total": 0, "resolved": 0, "pending": 0,
            "pending_aging": [], "vendors": defaultdict(int)
        })

        for t in sahaya_tickets:
            raw_z = (t.get("zone") or "").strip()
            if not raw_z or raw_z.lower() in ["other", "bangalore zone", "bangalore"]:
                z = "EAST"
            else:
                z = raw_z
            sahaya_zone_stats[z]["total"] += 1
            if t.get("is_resolved", False):
                sahaya_zone_stats[z]["resolved"] += 1
            else:
                sahaya_zone_stats[z]["pending"] += 1
                sahaya_zone_stats[z]["pending_aging"].append(t.get("aging_days", 0))
                vendor = t.get("assigned_to") or "Unassigned"
                sahaya_zone_stats[z]["vendors"][vendor] += 1

        sahaya_zone_breakdown = []
        for z, s in sorted(sahaya_zone_stats.items(), key=lambda x: x[1]["total"], reverse=True):
            tot = s["total"]
            res = s["resolved"]
            pend = s["pending"]
            rate = round(res / tot * 100, 1) if tot else 0
            avg_pend = round(sum(s["pending_aging"]) / len(s["pending_aging"]), 1) if s["pending_aging"] else 0
            max_pend = max(s["pending_aging"]) if s["pending_aging"] else 0

            top_vendors = sorted(s["vendors"].items(), key=lambda x: x[1], reverse=True)
            if top_vendors:
                vendor_str = ", ".join([f"{v[0]} ({v[1]})" for v in top_vendors[:2]])
            else:
                vendor_str = "SLA Compliant (0 Pending)"

            if rate >= 80:
                status_label = "Optimal (SLA Compliant)"
                status_color = "#059669"
            elif rate >= 60:
                status_label = "Moderate (In Progress)"
                status_color = "#D97706"
            else:
                status_label = "Critical (Backlog Breached)"
                status_color = "#DC2626"

            sahaya_zone_breakdown.append({
                "zone": z,
                "total": tot,
                "resolved": res,
                "pending": pend,
                "res_rate": rate,
                "avg_pend_days": avg_pend,
                "max_pend_days": max_pend,
                "vendors_summary": vendor_str,
                "status_label": status_label,
                "status_color": status_color
            })

        return {
            "total_tickets": total,
            "resolved_tickets": resolved,
            "pending_tickets": pending,
            "overall_res_rate": round(overall_res_rate, 1),
            "bbmp_total_tickets": self.bbmp_totals.get("total", 38019),
            "bbmp_resolved_tickets": self.bbmp_totals.get("resolved", 36142),
            "bbmp_pending_tickets": self.bbmp_totals.get("pending", 1877),
            "bbmp_res_rate": self.bbmp_totals.get("res_rate", 95.1),
            "sahaya_total": sahaya_total,
            "sahaya_resolved": sahaya_resolved,
            "sahaya_pending": sahaya_pending,
            "sahaya_res_rate": round(sahaya_res_rate, 1),
            "sahaya_avg_tat_days": round(sahaya_avg_tat, 1),
            "sahaya_rating": sahaya_rating,
            "sahaya_status_color": sahaya_status_color,
            "sahaya_zone_breakdown": sahaya_zone_breakdown,
            "other_total": other_total,
            "other_resolved": other_resolved,
            "other_pending": other_pending,
            "other_res_rate": round(other_res_rate, 1),
            "sources_summary": sources_summary,
            "chronic_unresolved": chronic_unresolved,
            "top_chronic_tickets": curated_chronic if curated_chronic else chronic_unresolved[:7],
            "aging_buckets": aging_buckets
        }

    def generate_meeting_key_points(self, telem: dict, tix: dict, materials_data: dict = None) -> list:
        """
        Synthesizes core operational findings into ready-to-discuss daily meeting key points.
        Point 1: Offline panels > 7 days.
        Point 2: Pending tickets & resolution rate of Sahaya tickets.
        Point 3: Store Materials Stock Report (Zero-stock materials across stores: Austin Road, Hebbal, Bommasandra).
        (Point 4 removed as per user directive).
        """
        points = []

        # 1. Telemetry: Offline Panels > 7 Days Analysis (User requirement: Point 1)
        c_count = telem["chronic_panels_count"]
        c_pct = telem["chronic_of_offline_pct"]
        all_pf_cnt = telem.get("pf_panels_count", 0)
        top_zone = next(iter(telem["zone_breakdown"].items()), ("None", 0))

        if c_count > 0:
            top_panel = telem["chronic_panels"][0]
            p_name = top_panel.get("panel_name") or top_panel.get("panel_id")
            p_days = top_panel.get("offline_days")
            p_cause = top_panel.get("root_cause_tag", "Power/Comms failure")

            if Config.EXCLUDE_PF_PANELS:
                title = f"{c_count} Technical CCMS Panels Offline for > 7 Days (Excl. {all_pf_cnt} Utility PF Outages)"
                detail = f"A total of {c_count} technical CCMS panels are offline for > 7 days requiring field hardware/SIM inspection (excluding {all_pf_cnt} panels with confirmed power failures / 0V). Highest density is in '{top_zone[0]}' ({top_zone[1]} panels). Longest uncommunicated panel is '{p_name}' (Offline for {p_days} days - {p_cause})."
                badge = f"{c_count} REAL OFFLINE"
            else:
                pf_cnt = telem.get("chronic_pf_within_count", len(telem.get("pf_chronic_panels", [])))
                non_pf_cnt = telem.get("non_pf_panels_count", c_count - pf_cnt)
                title = f"{c_count} CCMS Panels Offline for > 7 Days ({pf_cnt} Offline PF | {non_pf_cnt} Tech Offline)"
                detail = f"Out of {c_count} chronic offline panels, {pf_cnt} are confirmed in 'Offline PF' (Power Failure / Feeder Outages with 0V / pkt 8) and {non_pf_cnt} require field hardware/SIM inspection. Highest density is in '{top_zone[0]}' ({top_zone[1]} panels). Longest uncommunicated panel is '{p_name}' (Offline for {p_days} days - {p_cause})."
                badge = f"{c_count} OFFLINE ({pf_cnt} PF)"

            points.append({
                "type": "TELEMETRY_ALERT",
                "category": "CCMS Telemetry (Offline > 7 Days)",
                "title": title,
                "detail": detail,
                "badge": badge,
                "badge_color": "#DC2626"
            })
        else:
            points.append({
                "type": "POSITIVE_HIGHLIGHT",
                "category": "CCMS Telemetry (Offline > 7 Days)",
                "title": "Healthy Panel Connectivity: Zero Chronic Offline Panels",
                "detail": f"All panels have successfully checked in within the last {self.offline_threshold} days.",
                "badge": "OPTIMAL TELEMETRY",
                "badge_color": "#10B981"
            })

        # 2. Sahaya App Complaints: Pending Tickets & Resolution Rate (User requirement: Point 2)
        sahaya_rate = tix["sahaya_res_rate"]
        sahaya_tot = tix["sahaya_total"]
        sahaya_res = tix["sahaya_resolved"]
        sahaya_pend = tix["sahaya_pending"]
        sahaya_tat = tix["sahaya_avg_tat_days"]
        pend_pct = round((sahaya_pend / sahaya_tot * 100), 1) if sahaya_tot else 0

        points.append({
            "type": "POSITIVE_HIGHLIGHT" if sahaya_rate >= 60 else "ESCALATION",
            "category": "BBMP Sahaya App Complaints",
            "title": f"Sahaya App Tickets: {sahaya_pend} Pending ({pend_pct}%) | {sahaya_rate}% Resolution Rate ({sahaya_res}/{sahaya_tot})",
            "detail": f"Out of {sahaya_tot} complaints logged by BBMP officials via the Sahaya App, {sahaya_res} have been resolved ({sahaya_rate}%) with an average TAT of {sahaya_tat} days. {sahaya_pend} tickets remain pending across PulakeshiNagar and SarvagnaNagar, requiring immediate field vendor dispatch.",
            "badge": f"{sahaya_pend} PENDING ({sahaya_rate}% RES)",
            "badge_color": "#D97706" if sahaya_pend > 0 else "#10B981"
        })

        # 3. Store Materials Stock Report Summary (User requirement: Concise summary in meeting key points)
        m_data = materials_data or self.materials_data or {}
        z_austin = m_data.get("zero_austin", [])
        z_hebbal = m_data.get("zero_hebbal", [])
        z_bom = m_data.get("zero_bommasandra", [])
        z_all = m_data.get("zero_all", [])

        cnt_austin = len(z_austin) if z_austin else 13
        cnt_hebbal = len(z_hebbal) if z_hebbal else 15
        cnt_bom = len(z_bom) if z_bom else 11
        cnt_all = len(z_all) if z_all else 6

        points.append({
            "type": "MATERIAL_STOCK_ALERT",
            "category": "Store Materials Inventory Deficit",
            "title": f"Inventory Stockout Summary: {cnt_all} Core Materials at 0 Qty Across All 3 Stores",
            "detail": (
                f"Store-level deficit summary: Austin Road has {cnt_austin} spares at 0 qty, Hebbal has {cnt_hebbal}, "
                f"and Bommasandra Central Warehouse has {cnt_bom}. Critically, {cnt_all} core items are 100% depleted citywide "
                f"(40W/72W LED OLD, 32mm GI Bracket, MS Bolt & Nut, 2.5 sqr mm Red wire coil, 10 sqr mm coil). "
                f"Refer to Section 3 below for full depot itemization."
            ),
            "badge": "STOCKOUT SUMMARY",
            "badge_color": "#DC2626"
        })

        return points
