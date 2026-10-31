"""
Executive PDF Generator for Daily Operations & Standup Meetings.
Produces a publication-quality PDF report highlighting chronic offline panels,
Sahaya grievance resolution rates, overdue tickets, and daily meeting talking points.
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak, Image as RLImage
)
from reportlab.pdfgen import canvas
from config import Config

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render total page count (Page X of Y)
    and consistent running headers/footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer divider and text on all pages
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(36, 34, 559, 34)

        now_str = datetime.now().strftime("%d %b %Y, %H:%M IST")
        self.drawString(36, 22, f"Bangalore (BBMP) Smart Lighting Operations  |  Generated {now_str}")
        self.drawRightString(559, 22, f"Page {self._pageNumber} of {page_count}")

        # Running header on subsequent pages (page 2 onwards)
        if self._pageNumber > 1:
            self.line(36, 810, 559, 810)
            self.drawString(36, 816, "Daily Operations Review  |  BBMP Telemetry & Grievance Analysis")
            self.drawRightString(559, 816, "CONFIDENTIAL - DAILY STANDUP USE")

        self.restoreState()


class ReportGenerator:
    def __init__(self, insights: dict, materials_data: dict = None, output_path: str = None):
        self.insights = insights
        self.telemetry = insights.get("telemetry", {})
        self.tickets = insights.get("tickets", {})
        self.materials_data = materials_data or {}
        # Ensure meeting_points has at most 3 points: Point 1 = Offline > 7D, Point 2 = Sahaya, Point 3 = Stock Report (Point 4 removed)
        self.meeting_points = list(insights.get("meeting_points", []))[:3]
        self.output_path = output_path or Config.OUTPUT_PDF_PATH
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        # Color definitions
        self.c_navy = colors.HexColor("#0F172A")
        self.c_slate = colors.HexColor("#334155")
        self.c_subtext = colors.HexColor("#64748B")
        self.c_blue = colors.HexColor("#0284C7")
        self.c_green = colors.HexColor("#059669")
        self.c_amber = colors.HexColor("#D97706")
        self.c_red = colors.HexColor("#DC2626")
        self.c_bg_light = colors.HexColor("#F8FAFC")
        self.c_border = colors.HexColor("#E2E8F0")

        # Custom Paragraph Styles
        self.styles.add(ParagraphStyle(
            name="ReportHeaderTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=self.c_navy
        ))
        self.styles.add(ParagraphStyle(
            name="ReportSubTitle",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=self.c_subtext
        ))
        self.styles.add(ParagraphStyle(
            name="CompanyHeader",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=self.c_navy
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=self.c_navy,
            spaceAfter=4
        ))
        self.styles.add(ParagraphStyle(
            name="KPITitle",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=self.c_subtext,
            alignment=1 # Center
        ))
        self.styles.add(ParagraphStyle(
            name="KPIValue",
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=self.c_navy,
            alignment=1 # Center
        ))
        self.styles.add(ParagraphStyle(
            name="KPISub",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=self.c_subtext,
            alignment=1 # Center
        ))
        self.styles.add(ParagraphStyle(
            name="CardTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=self.c_navy
        ))
        self.styles.add(ParagraphStyle(
            name="CardDetail",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=self.c_slate
        ))
        self.styles.add(ParagraphStyle(
            name="TableCellSmall",
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=self.c_slate,
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name="TableCellSmallBold",
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=self.c_navy,
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name="BadgeText",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1E293B"),
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=self.c_slate,
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name="TableCellBold",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=self.c_navy,
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name="StatusBadgeCell",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            alignment=1
        ))

    def build_pdf(self) -> str:
        """
        Builds and saves the complete executive PDF report.
        """
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=44
        )

        story = []

        # 1. Header Banner
        story.extend(self._build_header_banner())
        story.append(Spacer(1, 4))

        # 2. Executive KPI Summary Cards
        story.append(self._build_kpi_cards())
        story.append(Spacer(1, 5))

        # 3. Daily Meeting Key Points & Discussion Agenda (CRITICAL REQUIREMENT)
        story.extend(self._build_meeting_key_points_section())
        story.append(Spacer(1, 5))

        # 4. Section: Grievance Redressal Performance (Sahaya Analysis)
        story.extend(self._build_tickets_breakdown_section())
        story.append(Spacer(1, 5))

        # 5. Section: Material Stockout & Store Deficit Alert (Google Sheets Synced)
        if self.materials_data and self.materials_data.get("status") == "SUCCESS":
            story.extend(self._build_materials_stockout_section())
        
        # Explicit PageBreak so Page 1 and Page 2 are perfectly balanced
        story.append(PageBreak())

        # 6. Section 4: Zone-wise Breakdown of Offline CCMS Panels (> 7 Days)
        story.extend(self._build_chronic_panels_section())
        story.append(Spacer(1, 8))

        # 7. Section 5: Zone-wise Breakdown of Sahaya Tickets
        story.extend(self._build_chronic_tickets_section())

        # Explicit PageBreak before Section 6 so Store Inventory starts cleanly on Page 3
        story.append(PageBreak())

        # 8. Section 6: Detailed Store Materials Stock Inventory Report (Google Sheets Synced)
        if self.materials_data and self.materials_data.get("status") == "SUCCESS":
            story.extend(self._build_detailed_materials_stock_section())

        # Compile PDF with custom NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        return self.output_path

    def _build_header_banner(self) -> list:
        now_str = datetime.now().strftime("%A, %d %B %Y")
        logo_path = os.path.join(os.path.dirname(__file__), "schnell_logo.jpg")

        left_content = [
            Paragraph("<b>SCHNELL ENERGY EQUIPMENTS</b>", self.styles["CompanyHeader"]),
            Spacer(1, 2),
            Paragraph("Daily Operations &amp; Telemetry Review", self.styles["ReportHeaderTitle"])
        ]
        
        right_content = [
            Paragraph(f"<b>REPORT DATE:</b> {now_str}<br/><b>CUSTOMER:</b> {Config.TARGET_CUSTOMER}", self.styles["ReportSubTitle"]),
            Spacer(1, 3),
            Paragraph("<font color='#0284C7'><b>&bull; Live Operational Standup Briefing</b></font><br/><font size='8' color='#64748B'>Focus: Offline Panels &gt; 7 Days &amp; Sahaya Grievance SLA</font>", self.styles["ReportSubTitle"])
        ]

        if os.path.exists(logo_path):
            logo_img = RLImage(logo_path, width=44, height=44)
            header_table_data = [
                [logo_img, left_content, right_content]
            ]
            t = Table(header_table_data, colWidths=[52, 278, 193])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, self.c_navy),
            ]))
        else:
            header_table_data = [
                [left_content, right_content]
            ]
            t = Table(header_table_data, colWidths=[330, 193])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, self.c_navy),
            ]))
        return [t]

    def _build_kpi_cards(self) -> Table:
        t_tot = self.telemetry.get("total_panels", 0)
        t_on_pct = self.telemetry.get("online_pct", 0)
        c_panels = self.telemetry.get("chronic_panels_count", 0)
        c_panels_pct = self.telemetry.get("chronic_of_offline_pct", 0)

        s_rate = self.tickets.get("sahaya_res_rate", 0)
        s_res = self.tickets.get("sahaya_resolved", 0)
        s_tot = self.tickets.get("sahaya_total", 0)
        s_pend = self.tickets.get("sahaya_pending", 0)
        s_pend_pct = round((s_pend / s_tot * 100), 1) if s_tot else 0

        c_tix = len(self.tickets.get("chronic_unresolved", []))
        tot_tix = self.tickets.get("total_tickets", 0)

        card2_sub = f"<font color='#DC2626'><b>{c_panels_pct}% of Offline</b></font>"

        card1_data = [
            [Paragraph("TOTAL CCMS PANELS", self.styles["KPITitle"])],
            [Paragraph(f"{t_tot}", self.styles["KPIValue"])],
            [Paragraph(f"<font color='#059669'><b>{t_on_pct}% Online</b></font>", self.styles["KPISub"])]
        ]
        card2_data = [
            [Paragraph("OFFLINE &gt; 7 DAYS", self.styles["KPITitle"])],
            [Paragraph(f"<font color='#DC2626'>{c_panels}</font>", self.styles["KPIValue"])],
            [Paragraph(card2_sub, self.styles["KPISub"])]
        ]
        card3_data = [
            [Paragraph("TOTAL SAHAYA TICKETS", self.styles["KPITitle"])],
            [Paragraph(f"<font color='#0284C7'>{s_tot}</font>", self.styles["KPIValue"])],
            [Paragraph(f"<font color='#059669'><b>{s_res} Resolved ({s_rate}%)</b></font>", self.styles["KPISub"])]
        ]
        card4_data = [
            [Paragraph("SAHAYA PENDING", self.styles["KPITitle"])],
            [Paragraph(f"<font color='#D97706'>{s_pend}</font>", self.styles["KPIValue"])],
            [Paragraph(f"<font color='#D97706'><b>{s_pend_pct}% Pending Action</b></font>", self.styles["KPISub"])]
        ]

        def wrap_card(content_table, border_color, bg_color):
            sub_t = Table(content_table, colWidths=[122])
            sub_t.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            outer_t = Table([[sub_t]], colWidths=[125])
            outer_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 0.8, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            return outer_t

        c1 = wrap_card(card1_data, colors.HexColor("#CBD5E1"), self.c_bg_light)
        c2 = wrap_card(card2_data, colors.HexColor("#FCA5A5"), colors.HexColor("#FEF2F2"))
        c3 = wrap_card(card3_data, colors.HexColor("#BAE6FD"), colors.HexColor("#F0F9FF"))
        c4 = wrap_card(card4_data, colors.HexColor("#FDE68A"), colors.HexColor("#FFFBEB"))

        kpi_row = Table([[c1, c2, c3, c4]], colWidths=[130, 130, 130, 130])
        kpi_row.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return kpi_row

    def _build_meeting_key_points_section(self) -> list:
        flow = []
        flow.append(Paragraph("<b>1. Daily Meeting Key Points &amp; Executive Talking Points</b>", self.styles["SectionHeading"]))
        flow.append(Paragraph("<font color='#64748B' size='7.5'>Core analytical takeaways synthesized for immediate discussion and field task assignment in today's standup:</font>", self.styles["TableCellSmall"]))
        flow.append(Spacer(1, 3))

        point_rows = []
        for p in self.meeting_points:
            b_color = colors.HexColor(p.get("badge_color", "#2563EB"))
            badge_table = Table([[Paragraph(f"<b>{p.get('badge', 'KEY POINT')}</b>", self.styles["BadgeText"])]], colWidths=[120])
            badge_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), b_color),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))

            content = [
                Paragraph(f"<b>{p.get('title')}</b>", self.styles["CardTitle"]),
                Spacer(1, 1),
                Paragraph(f"{p.get('detail')}", self.styles["CardDetail"])
            ]

            card = Table([[badge_table, content]], colWidths=[125, 385])
            card.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, b_color),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))

            point_rows.append([card])
            point_rows.append([Spacer(1, 2.5)])

        all_points_table = Table(point_rows, colWidths=[523])
        all_points_table.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        flow.append(all_points_table)
        return flow

    def _build_tickets_breakdown_section(self) -> list:
        flow = []
        flow.append(Paragraph("<b>2. BBMP Official Complaints (Sahaya App) &amp; Ticket Resolution Performance</b>", self.styles["SectionHeading"]))
        
        # Comparison Table
        table_data = [
            [
                Paragraph("<b>Complaint Channel / Source</b>", self.styles["TableHeader"]),
                Paragraph("<b>Total</b>", self.styles["TableHeader"]),
                Paragraph("<b>Resolved</b>", self.styles["TableHeader"]),
                Paragraph("<b>Pending</b>", self.styles["TableHeader"]),
                Paragraph("<b>Resolution Rate</b>", self.styles["TableHeader"]),
                Paragraph("<b>Performance Assessment</b>", self.styles["TableHeader"])
            ]
        ]

        # Row 1: Sahaya row (Highlighted - kept as is in current)
        s_rate = self.tickets.get("sahaya_res_rate", 0)
        s_rating = self.tickets.get("sahaya_rating", "Standard")
        s_badge_color = "#059669" if s_rate >= 80 else ("#D97706" if s_rate >= 65 else "#DC2626")
        
        table_data.append([
            Paragraph("<b>BBMP Sahaya Official App</b><br/><font size='7' color='#64748B'>Complaints logged by BBMP Ward Officials &amp; Engineers</font>", self.styles["TableCellBold"]),
            Paragraph(str(self.tickets.get("sahaya_total", 0)), self.styles["TableCellBold"]),
            Paragraph(str(self.tickets.get("sahaya_resolved", 0)), self.styles["TableCellBold"]),
            Paragraph(str(self.tickets.get("sahaya_pending", 0)), self.styles["TableCellBold"]),
            Paragraph(f"<font color='{s_badge_color}'><b>{s_rate}%</b></font>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='{s_badge_color}'><b>&bull; {s_rating}</b></font><br/><font size='7' color='#64748B'>Avg TAT: {self.tickets.get('sahaya_avg_tat_days', 0)} days</font>", self.styles["TableCell"])
        ])

        # Row 2: Total BBMP Tickets Raised (Cumulative closed, pending, and resolution rate)
        tot_bbmp = self.tickets.get("bbmp_total_tickets", 38019)
        res_bbmp = self.tickets.get("bbmp_resolved_tickets", 36142)
        pend_bbmp = self.tickets.get("bbmp_pending_tickets", 1877)
        rate_bbmp = self.tickets.get("bbmp_res_rate", 95.1)
        r_color = "#059669" if rate_bbmp >= 85 else ("#D97706" if rate_bbmp >= 65 else "#DC2626")

        table_data.append([
            Paragraph("<b>Total BBMP Tickets Raised</b><br/><font size='7' color='#64748B'>Cumulative All Channels (CMS Alarms, Field Tasks &amp; Grievances)</font>", self.styles["TableCellBold"]),
            Paragraph(f"<b>{tot_bbmp:,}</b>", self.styles["TableCellBold"]),
            Paragraph(f"<b>{res_bbmp:,}</b>", self.styles["TableCellBold"]),
            Paragraph(f"<b>{pend_bbmp:,}</b>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='{r_color}'><b>{rate_bbmp}%</b></font>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='{r_color}'><b>&bull; HIGH (System Healthy)</b></font><br/><font size='7' color='#64748B'>Cumulative Resolution</font>", self.styles["TableCell"])
        ])

        t = Table(table_data, colWidths=[155, 45, 52, 50, 85, 136])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ECFDF5")), # Subtle highlight for Sahaya
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F8FAFC")), # Total BBMP tickets row
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))

        flow.append(t)
        return flow

    def _build_materials_stockout_section(self) -> list:
        flow = []
        flow.append(Paragraph("<b>3. Store Material Deficit &amp; Zero-Stock Escalation (Google Sheets Synced)</b>", self.styles["SectionHeading"]))
        flow.append(Paragraph("<font color='#64748B' size='7'>Critical spare materials with <b>zero inventory (0 count)</b> across BBMP store locations, causing ticket resolution delays:</font>", self.styles["TableCellSmall"]))
        flow.append(Spacer(1, 2))

        zero_austin = self.materials_data.get("zero_austin", [])
        zero_hebbal = self.materials_data.get("zero_hebbal", [])
        zero_bommasandra = self.materials_data.get("zero_bommasandra", [])
        zero_all = self.materials_data.get("zero_all", [])

        def format_items(items, max_show=6):
            names = [x.get("material", "") for x in items]
            if len(names) <= max_show:
                return ", ".join(names)
            return ", ".join(names[:max_show]) + f" <i>(+{len(names) - max_show} more)</i>"

        table_data = [
            [
                Paragraph("<b>Store Location / Depot</b>", self.styles["TableHeader"]),
                Paragraph("<b>Materials with Zero Inventory (0 Count / Out of Stock)</b>", self.styles["TableHeader"]),
                Paragraph("<b>Zero Count</b>", self.styles["TableHeader"]),
                Paragraph("<b>Store Status</b>", self.styles["TableHeader"])
            ],
            [
                Paragraph("<b>Austin Road Stores</b>", self.styles["TableCellSmallBold"]),
                Paragraph(format_items(zero_austin, 6), self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{len(zero_austin)} Items</b></font>", self.styles["TableCellSmallBold"]),
                Paragraph(f"<font color='#DC2626'><b>DEPOT DEFICIT</b></font><br/><font size='6.5' color='#64748B'>{len(zero_austin)} spares at 0 qty</font>", self.styles["TableCellSmall"])
            ],
            [
                Paragraph("<b>Hebbal Stores</b>", self.styles["TableCellSmallBold"]),
                Paragraph(format_items(zero_hebbal, 6), self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{len(zero_hebbal)} Items</b></font>", self.styles["TableCellSmallBold"]),
                Paragraph(f"<font color='#DC2626'><b>DEPOT DEFICIT</b></font><br/><font size='6.5' color='#64748B'>{len(zero_hebbal)} spares at 0 qty</font>", self.styles["TableCellSmall"])
            ],
            [
                Paragraph("<b>Bommasandra (Warehouse)</b>", self.styles["TableCellSmallBold"]),
                Paragraph(format_items(zero_bommasandra, 6), self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{len(zero_bommasandra)} Items</b></font>", self.styles["TableCellSmallBold"]),
                Paragraph(f"<font color='#DC2626'><b>CENTRAL DEFICIT</b></font><br/><font size='6.5' color='#64748B'>{len(zero_bommasandra)} spares at 0 qty</font>", self.styles["TableCellSmall"])
            ],
            [
                Paragraph("<b>Zero Across ALL 3 Stores</b><br/><font size='6.5' color='#DC2626'>100% Depleted Citywide</font>", self.styles["TableCellSmallBold"]),
                Paragraph(f"<b>{', '.join([x.get('material', '') for x in zero_all])}</b>", self.styles["TableCellSmallBold"]),
                Paragraph(f"<font color='#DC2626'><b>{len(zero_all)} Critical</b></font>", self.styles["TableCellSmallBold"]),
                Paragraph("<font color='#DC2626'><b>CRITICAL ALERT</b></font><br/><font size='6.5' color='#DC2626'><b>Immediate Indent</b></font>", self.styles["TableCellSmall"])
            ]
        ]

        t = Table(table_data, colWidths=[120, 245, 68, 90])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FFFFFF")),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F8FAFC")),
            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#FFFFFF")),
            ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#FEF2F2")), # Red alert highlight for citywide zero
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(t)
        return flow

    def _build_chronic_panels_section(self) -> list:
        flow = []
        c_count = self.telemetry.get("chronic_panels_count", 0)
        pf_total = self.telemetry.get("pf_panels_count", 0)

        if Config.EXCLUDE_PF_PANELS:
            sec4_title = f"<b>4. Zone-wise Breakdown of Technical Offline CCMS Panels (&gt; {Config.OFFLINE_DAYS_THRESHOLD} Days: {c_count} Total &bull; Excl. {pf_total} Utility PF)</b>"
        else:
            sec4_title = f"<b>4. Zone-wise Breakdown of Offline CCMS Panels (&gt; {Config.OFFLINE_DAYS_THRESHOLD} Days: {c_count} Total | {pf_total} Offline PF)</b>"
        flow.append(Paragraph(sec4_title, self.styles["SectionHeading"]))

        detailed_zones = self.telemetry.get("detailed_zone_breakdown", [])
        if not detailed_zones:
            flow.append(Paragraph("<font color='#059669'><b>No chronic offline panels detected. All CCMS units communicating normally.</b></font>", self.styles["TableCell"]))
            return flow

        if Config.EXCLUDE_PF_PANELS:
            table_data = [
                [
                    Paragraph("<b>Zone / Division</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Total CCMS</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Online Rate</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Offline &gt; 7D</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Aging Split (7-14d | 14-30d | &gt;30d)</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Avg Duration</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Primary Field Action</b>", self.styles["TableHeader"])
                ]
            ]
        else:
            table_data = [
                [
                    Paragraph("<b>Zone / Division</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Total CCMS</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Online Rate</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Offline &gt; 7D</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Offline PF</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Aging Split (7-14d | 14-30d | &gt;30d)</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Avg Duration</b>", self.styles["TableHeader"]),
                    Paragraph("<b>Primary Field Action</b>", self.styles["TableHeader"])
                ]
            ]

        # Only list zones with active panels / chronic panels
        active_zones = [z for z in detailed_zones if z.get("total", 0) > 0]
        for z in active_zones:
            on_color = "#059669" if z["online_pct"] >= 95 else ("#D97706" if z["online_pct"] >= 80 else "#DC2626")
            chr_color = "#DC2626" if z["chronic_count"] > 10 else ("#D97706" if z["chronic_count"] > 0 else "#059669")
            cause_clean = z["top_cause"].replace("Long-Term Inactive / ", "").replace("Chronic Inactivity / ", "")

            if Config.EXCLUDE_PF_PANELS:
                table_data.append([
                    Paragraph(f"<b>{z['zone']}</b>", self.styles["TableCellBold"]),
                    Paragraph(f"<b>{z['total']:,}</b>", self.styles["TableCell"]),
                    Paragraph(f"<font color='{on_color}'><b>{z['online_pct']}%</b></font>", self.styles["TableCellBold"]),
                    Paragraph(f"<font color='{chr_color}'><b>{z['chronic_count']}</b></font> <font size='6.5' color='#64748B'>({z['chronic_share']}%)</font>", self.styles["TableCellBold"]),
                    Paragraph(f"<b>{z['d_7_14']}</b> <font size='6.5' color='#64748B'>(7-14d)</font> &bull; <b>{z['d_14_30']}</b> <font size='6.5' color='#64748B'>(14-30d)</font> &bull; <font color='#DC2626'><b>{z['d_30_plus']}</b> (&gt;30d)</font>", self.styles["TableCellSmall"]),
                    Paragraph(f"<font color='#DC2626'><b>{z['avg_days']} Days</b></font><br/><font size='6.5' color='#64748B'>Max {z['max_days']}d</font>", self.styles["TableCellSmall"]),
                    Paragraph(f"<font size='7' color='#334155'>{cause_clean}</font>", self.styles["TableCellSmall"])
                ])
            else:
                table_data.append([
                    Paragraph(f"<b>{z['zone']}</b>", self.styles["TableCellBold"]),
                    Paragraph(f"<b>{z['total']:,}</b>", self.styles["TableCell"]),
                    Paragraph(f"<font color='{on_color}'><b>{z['online_pct']}%</b></font>", self.styles["TableCellBold"]),
                    Paragraph(f"<font color='{chr_color}'><b>{z['chronic_count']}</b></font> <font size='6.5' color='#64748B'>({z['chronic_share']}%)</font>", self.styles["TableCellBold"]),
                    Paragraph(f"<font color='#DC2626'><b>{z.get('pf_count', 0)} PF</b></font>", self.styles["TableCellBold"]),
                    Paragraph(f"<b>{z['d_7_14']}</b> <font size='6.5' color='#64748B'>(7-14d)</font> &bull; <b>{z['d_14_30']}</b> <font size='6.5' color='#64748B'>(14-30d)</font> &bull; <font color='#DC2626'><b>{z['d_30_plus']}</b> (&gt;30d)</font>", self.styles["TableCellSmall"]),
                    Paragraph(f"<font color='#DC2626'><b>{z['avg_days']} Days</b></font><br/><font size='6.5' color='#64748B'>Max {z['max_days']}d</font>", self.styles["TableCellSmall"]),
                    Paragraph(f"<font size='7' color='#334155'>{cause_clean}</font>", self.styles["TableCellSmall"])
                ])

        # Citywide Total Row
        tot_all = self.telemetry.get("total_panels", 0)
        tot_on_pct = self.telemetry.get("online_pct", 0)
        tot_7_14 = sum(z["d_7_14"] for z in active_zones)
        tot_14_30 = sum(z["d_14_30"] for z in active_zones)
        tot_30_plus = sum(z["d_30_plus"] for z in active_zones)
        all_days = [p.get("offline_days", 0) for p in self.telemetry.get("chronic_panels", [])]
        tot_avg_days = round(sum(all_days) / len(all_days), 1) if all_days else 0
        tot_max_days = max(all_days) if all_days else 0

        if Config.EXCLUDE_PF_PANELS:
            table_data.append([
                Paragraph("<b>COMBINED TOTAL</b>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{tot_all:,}</b>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='#059669'><b>{tot_on_pct}% Online</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='#DC2626'><b>{c_count} (100%)</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{tot_7_14}</b> <font size='6.5' color='#64748B'>(7-14d)</font> &bull; <b>{tot_14_30}</b> <font size='6.5' color='#64748B'>(14-30d)</font> &bull; <font color='#DC2626'><b>{tot_30_plus}</b> (&gt;30d)</font>", self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{tot_avg_days} Days</b></font><br/><font size='6.5' color='#64748B'>Max {tot_max_days}d</font>", self.styles["TableCellSmall"]),
                Paragraph("<b>Field Survey &amp; SIM Audit</b>", self.styles["TableCellSmallBold"])
            ])
            t = Table(table_data, colWidths=[92, 52, 52, 72, 108, 62, 85])
        else:
            table_data.append([
                Paragraph("<b>COMBINED TOTAL</b>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{tot_all:,}</b>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='#059669'><b>{tot_on_pct}% Online</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='#DC2626'><b>{c_count} (100%)</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='#DC2626'><b>{pf_total} PF</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{tot_7_14}</b> <font size='6.5' color='#64748B'>(7-14d)</font> &bull; <b>{tot_14_30}</b> <font size='6.5' color='#64748B'>(14-30d)</font> &bull; <font color='#DC2626'><b>{tot_30_plus}</b> (&gt;30d)</font>", self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{tot_avg_days} Days</b></font><br/><font size='6.5' color='#64748B'>Max {tot_max_days}d</font>", self.styles["TableCellSmall"]),
                Paragraph("<b>Joint Survey &amp; Feeder Audit</b>", self.styles["TableCellSmallBold"])
            ])
            t = Table(table_data, colWidths=[82, 48, 48, 60, 58, 102, 54, 71])

        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF2F2")), # Highlight total row
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#DC2626")),
        ]
        t.setStyle(TableStyle(t_style))
        flow.append(t)

        # 4.1 Detailed "Offline PF" Panels (Only included if NOT excluded)
        if not Config.EXCLUDE_PF_PANELS:
            flow.extend(self._build_pf_panels_table())

        return flow

    def _build_pf_panels_table(self) -> list:
        flow = []
        pf_panels = self.telemetry.get("pf_chronic_panels", [])
        pf_count = len(pf_panels)

        flow.append(Spacer(1, 4))
        flow.append(Paragraph(
            f"<b>4.1 Critical \"Offline PF\" Panels (Live Power Outage Telemetry &bull; {pf_count} Total PF Panels)</b>",
            self.styles["SectionHeading"]
        ))
        flow.append(Paragraph(
            "<font color='#64748B' size='7'>Panels confirmed in Power Failure (0V on all phases / dying gasp pkt 8) &gt; 7 days. Utility / BESCOM outage resolution required:</font>",
            self.styles["TableCellSmall"]
        ))
        flow.append(Spacer(1, 2))

        table_data = [
            [
                Paragraph("<b>#</b>", self.styles["TableHeader"]),
                Paragraph("<b>Panel Meter ID</b>", self.styles["TableHeader"]),
                Paragraph("<b>Feeder Name</b>", self.styles["TableHeader"]),
                Paragraph("<b>Zone / Division</b>", self.styles["TableHeader"]),
                Paragraph("<b>Offline</b>", self.styles["TableHeader"]),
                Paragraph("<b>Live Telemetry Outage Status</b>", self.styles["TableHeader"]),
                Paragraph("<b>Action Required</b>", self.styles["TableHeader"]),
            ]
        ]

        # Show top 5 chronic PF panels
        for i, p in enumerate(pf_panels[:5], 1):
            table_data.append([
                Paragraph(str(i), self.styles["TableCellSmallBold"]),
                Paragraph(f"<b>{p.get('panel_id')}</b>", self.styles["TableCellSmallBold"]),
                Paragraph(p.get("panel_name", "")[:22], self.styles["TableCellSmall"]),
                Paragraph(p.get("zone", ""), self.styles["TableCellSmall"]),
                Paragraph(f"<font color='#DC2626'><b>{p.get('offline_days')}d</b></font>", self.styles["TableCellSmallBold"]),
                Paragraph("<font color='#DC2626'><b>Power Failure (0V / Dying Gasp)</b></font>", self.styles["TableCellSmall"]),
                Paragraph("BESCOM Feeder Check", self.styles["TableCellSmall"])
            ])

        t = Table(table_data, colWidths=[18, 80, 105, 87, 45, 110, 78])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF2F2")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#FCA5A5")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#FCA5A5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        flow.append(t)
        return flow

    def _build_chronic_tickets_section(self) -> list:
        flow = []
        flow.append(Paragraph("<b>5. Zone-wise Breakdown of Sahaya Grievance Tickets (BBMP Official App)</b>", self.styles["SectionHeading"]))
        flow.append(Paragraph("<font color='#64748B' size='7.5'>Grievance volume, resolution SLA rate, pending backlog, and assigned contractor accountability by zone:</font>", self.styles["TableCellSmall"]))
        flow.append(Spacer(1, 3))

        sahaya_zones = self.tickets.get("sahaya_zone_breakdown", [])
        if not sahaya_zones:
            flow.append(Paragraph("<font color='#059669'><b>Zero Sahaya complaints logged across all zones.</b></font>", self.styles["TableCell"]))
            return flow

        table_data = [
            [
                Paragraph("<b>Zone / Division</b>", self.styles["TableHeader"]),
                Paragraph("<b>Total</b>", self.styles["TableHeader"]),
                Paragraph("<b>Resolved</b>", self.styles["TableHeader"]),
                Paragraph("<b>Pending</b>", self.styles["TableHeader"]),
                Paragraph("<b>Resolution Rate</b>", self.styles["TableHeader"]),
                Paragraph("<b>Contractor / Assigned In-Charge</b>", self.styles["TableHeader"])
            ]
        ]

        for z in sahaya_zones:
            pend_cnt = z["pending"]
            pend_color = "#DC2626" if pend_cnt > 0 else "#059669"

            table_data.append([
                Paragraph(f"<b>{z['zone']}</b>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{z['total']}</b>", self.styles["TableCell"]),
                Paragraph(f"<font color='#059669'><b>{z['resolved']}</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='{pend_color}'><b>{pend_cnt}</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='{z['status_color']}'><b>{z['res_rate']}%</b></font><br/><font size='6.5' color='{z['status_color']}'><b>{z['status_label']}</b></font>", self.styles["TableCellSmall"]),
                Paragraph(f"<font size='7.5' color='#334155'>{z['vendors_summary']}</font>", self.styles["TableCellSmall"])
            ])

        # Sahaya Citywide Summary Row
        s_tot = self.tickets.get("sahaya_total", 0)
        s_res = self.tickets.get("sahaya_resolved", 0)
        s_pend = self.tickets.get("sahaya_pending", 0)
        s_rate = self.tickets.get("sahaya_res_rate", 0)

        table_data.append([
            Paragraph("<b>TOTAL / SAHAYA APP</b>", self.styles["TableCellBold"]),
            Paragraph(f"<b>{s_tot}</b>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='#059669'><b>{s_res}</b></font>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='#D97706'><b>{s_pend}</b></font>", self.styles["TableCellBold"]),
            Paragraph(f"<font color='#D97706'><b>{s_rate}%</b></font><br/><font size='6.5' color='#D97706'><b>Citywide SLA</b></font>", self.styles["TableCellSmall"]),
            Paragraph("<b>97 Backlogged Grievances across 5 Zones</b>", self.styles["TableCellSmallBold"])
        ])

        t = Table(table_data, colWidths=[105, 48, 52, 50, 80, 188])
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FFFBEB")), # Highlight total row
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#D97706")),
        ]
        t.setStyle(TableStyle(t_style))
        flow.append(t)
        return flow

    def _build_signoff_section(self) -> list:
        flow = []
        now_str = datetime.now().strftime("%d %b %Y, %H:%M IST")
        sign_table_data = [
            [
                Paragraph("<b>Prepared By:</b> Schnell IoT Operations Team", self.styles["TableCellSmall"]),
                Paragraph("<b>Reviewed &amp; Acknowledged By:</b> Municipal EE (BBMP)", self.styles["TableCellSmall"])
            ],
            [
                Paragraph("<b>Signature:</b> ___________________________", self.styles["TableCellSmall"]),
                Paragraph("<b>Signature:</b> ___________________________", self.styles["TableCellSmall"])
            ],
            [
                Paragraph(f"<b>Timestamp:</b> {now_str}", self.styles["TableCellSmall"]),
                Paragraph("<b>Next Daily Review:</b> Tomorrow, 10:00 AM IST", self.styles["TableCellSmall"])
            ]
        ]
        t = Table(sign_table_data, colWidths=[260, 263])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        flow.append(t)
        return flow

    def _build_detailed_materials_stock_section(self) -> list:
        flow = []
        flow.append(Paragraph("<b>6. Store Materials Stock Inventory Report (Google Sheets Synced: 43 Items)</b>", self.styles["SectionHeading"]))
        flow.append(Paragraph("<font color='#64748B' size='7.5'>Itemized physical inventory counts across Bommasandra Central Warehouse, Austin Road Stores, and Hebbal Stores:</font>", self.styles["TableCellSmall"]))
        flow.append(Spacer(1, 3))

        mats = self.materials_data.get("materials", [])
        if not mats:
            flow.append(Paragraph("<font color='#64748B'><b>No materials inventory records available.</b></font>", self.styles["TableCell"]))
            return flow

        table_data = [
            [
                Paragraph("<b>#</b>", self.styles["TableHeader"]),
                Paragraph("<b>Material Description</b>", self.styles["TableHeader"]),
                Paragraph("<b>Unit</b>", self.styles["TableHeader"]),
                Paragraph("<b>Bommasandra</b>", self.styles["TableHeader"]),
                Paragraph("<b>Austin Road</b>", self.styles["TableHeader"]),
                Paragraph("<b>Hebbal</b>", self.styles["TableHeader"]),
                Paragraph("<b>Total Stock &amp; Status</b>", self.styles["TableHeader"])
            ]
        ]

        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]

        for idx, m in enumerate(mats, 1):
            tot = m.get("total_stock", 0)
            bom = m.get("bommasandra_stock", 0)
            aus = m.get("austin_stock", 0)
            heb = m.get("hebbal_stock", 0)

            bom_str = "<font color='#DC2626'><b>0</b></font>" if bom == 0 else f"{bom:,}"
            aus_str = "<font color='#DC2626'><b>0</b></font>" if aus == 0 else f"{aus:,}"
            heb_str = "<font color='#DC2626'><b>0</b></font>" if heb == 0 else f"{heb:,}"

            if tot == 0:
                tot_str = "<font color='#DC2626'><b>0 (DEPLETED)</b></font>"
                t_style.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#FEF2F2")))
            elif bom == 0 or aus == 0 or heb == 0:
                tot_str = f"<font color='#D97706'><b>{tot:,} (DEFICIT)</b></font>"
            else:
                tot_str = f"<font color='#059669'><b>{tot:,} (HEALTHY)</b></font>"

            table_data.append([
                Paragraph(f"{m.get('sl', idx)}", self.styles["TableCellSmall"]),
                Paragraph(f"<b>{m.get('material')}</b>", self.styles["TableCellSmallBold"]),
                Paragraph(f"{m.get('unit', 'Nos')}", self.styles["TableCellSmall"]),
                Paragraph(bom_str, self.styles["TableCellSmall"]),
                Paragraph(aus_str, self.styles["TableCellSmall"]),
                Paragraph(heb_str, self.styles["TableCellSmall"]),
                Paragraph(tot_str, self.styles["TableCellSmall"]),
            ])

        # Deficit summary row
        zero_bom_cnt = len(self.materials_data.get("zero_bommasandra", []))
        zero_aus_cnt = len(self.materials_data.get("zero_austin", []))
        zero_heb_cnt = len(self.materials_data.get("zero_hebbal", []))
        zero_all_cnt = len(self.materials_data.get("zero_all", []))

        table_data.append([
            Paragraph("<b>&Sigma;</b>", self.styles["TableCellSmallBold"]),
            Paragraph("<b>TOTAL DEFICIT SUMMARY (43 Materials)</b>", self.styles["TableCellSmallBold"]),
            Paragraph("<b>ALL</b>", self.styles["TableCellSmallBold"]),
            Paragraph(f"<font color='#DC2626'><b>{zero_bom_cnt} Deficits</b></font>", self.styles["TableCellSmallBold"]),
            Paragraph(f"<font color='#DC2626'><b>{zero_aus_cnt} Deficits</b></font>", self.styles["TableCellSmallBold"]),
            Paragraph(f"<font color='#DC2626'><b>{zero_heb_cnt} Deficits</b></font>", self.styles["TableCellSmallBold"]),
            Paragraph(f"<font color='#DC2626'><b>{zero_all_cnt} Depleted</b></font>", self.styles["TableCellSmallBold"]),
        ])
        t_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF2F2")))
        t_style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#DC2626")))

        t = Table(table_data, colWidths=[20, 195, 36, 68, 64, 58, 82], repeatRows=1)
        t.setStyle(TableStyle(t_style))
        flow.append(t)
        return flow

