"""
Email Dispatch Module.
Sends the generated Daily Operations Review executive PDF report via SMTP email
with a clean, concise text message directing to the PDF attachment.
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from config import Config

logger = logging.getLogger("EmailSender")

class EmailSender:
    def __init__(self, config=None):
        self.config = config or Config
        self.smtp_host = self.config.SMTP_HOST
        self.smtp_port = self.config.SMTP_PORT
        self.username = self.config.SMTP_USERNAME
        self.password = self.config.SMTP_PASSWORD
        self.use_tls = self.config.SMTP_USE_TLS
        self.use_ssl = self.config.SMTP_USE_SSL
        self.sender = self.config.EMAIL_SENDER or self.username
        self.recipients = self.config.EMAIL_RECIPIENTS
        self.cc = self.config.EMAIL_CC
        self.subject = self.config.EMAIL_SUBJECT

    def is_configured(self) -> bool:
        """Checks whether minimum SMTP settings and recipients are provided."""
        if not self.smtp_host:
            logger.warning("SMTP_HOST is not configured.")
            return False
        if not self.username:
            logger.warning("SMTP_USERNAME is not configured.")
            return False
        if not self.password:
            logger.warning("SMTP_PASSWORD is not configured.")
            return False
        if not self.recipients:
            logger.warning("EMAIL_RECIPIENTS is not configured.")
            return False
        return True

    def build_plain_text(self) -> str:
        """Simple plain text message leading to the attached PDF."""
        return (
            "Good morning,\n\n"
            f"Please find attached today's Daily Operations & Telemetry Review PDF report for {self.config.TARGET_CUSTOMER}.\n\n"
            "The attached PDF contains the complete operational details regarding CCMS panel connectivity, "
            "grievance redressal metrics, and store materials inventory status.\n\n"
            "Best regards,\n"
            f"{self.config.ORGANIZATION_NAME}\n"
        )

    def build_html_body(self) -> str:
        """Clean HTML email text without dashboard widgets, leading directly to the PDF."""
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #222222; line-height: 1.6; margin: 20px;">
  <p>Good morning,</p>
  <p>Please find attached today's <strong>Daily Operations &amp; Telemetry Review</strong> PDF report for {self.config.TARGET_CUSTOMER}.</p>
  <p>The attached PDF contains the complete operational details regarding CCMS panel connectivity, grievance redressal metrics, and store materials inventory status.</p>
  <br>
  <p>Best regards,<br>
  <strong>{self.config.ORGANIZATION_NAME}</strong></p>
</body>
</html>
"""

    def send_report_email(self, pdf_path: str = None, insights: dict = None, materials_data: dict = None) -> bool:
        """
        Sends the PDF file to configured recipients.
        Returns True on success, False on failure.
        """
        pdf_file = pdf_path or self.config.OUTPUT_PDF_PATH
        if not os.path.exists(pdf_file):
            logger.error(f"Cannot send email: PDF file '{pdf_file}' not found.")
            return False

        if not self.is_configured():
            logger.error("Cannot send email: Missing required SMTP configuration in .env.")
            return False

        today_str = datetime.now().strftime("%d-%b-%Y")
        subject = f"{self.subject} [{today_str}]"

        msg = MIMEMultipart("mixed")
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        if self.cc:
            msg["Cc"] = ", ".join(self.cc)
        msg["Subject"] = subject

        # Body: Plain text + HTML fallback (no dashboard, just clean message)
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(self.build_plain_text(), "plain", "utf-8"))
        body_part.attach(MIMEText(self.build_html_body(), "html", "utf-8"))
        msg.attach(body_part)

        # PDF Attachment
        try:
            with open(pdf_file, "rb") as f:
                pdf_data = f.read()
            part = MIMEApplication(pdf_data, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_file))
            msg.attach(part)
        except Exception as e:
            logger.error(f"Failed to attach PDF report: {e}")
            return False

        all_recipients = list(self.recipients) + list(self.cc)

        logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                if self.use_tls:
                    server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(self.sender, all_recipients, msg.as_string())
            server.quit()

            logger.info(f"Email successfully dispatched to: {', '.join(all_recipients)}")
            print("\n" + "="*70)
            print("  EMAIL SENT SUCCESSFULLY!")
            print(f"  Recipients: {', '.join(self.recipients)}")
            if self.cc:
                print(f"  CC        : {', '.join(self.cc)}")
            print(f"  Subject   : {subject}")
            print(f"  Attachment: {os.path.basename(pdf_file)}")
            print("="*70 + "\n")
            return True

        except Exception as e:
            logger.error(f"Failed to send report email via SMTP: {e}")
            return False

if __name__ == "__main__":
    sender = EmailSender()
    if sender.is_configured():
        sender.send_report_email()
    else:
        print("SMTP is not yet configured. Please fill in SMTP credentials in .env file.")
