"""
gmail_sender.py - Cold outreach email dispatching engine via Gmail SMTP.
Features dual SMTP negotiation (587 STARTTLS / 465 SSL), dynamic 60+ JD keyword hooking,
anti-throttling delays, non-ASCII sanitization, randomized attachment timestamping,
and de-duplication against email_sent_history.csv.
"""

import os
import re
import sys
import time
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import make_msgid, formatdate
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from client_config import (
    BASE_DIR,
    EMAIL_SENT_HISTORY_CSV,
    RECRUITERS_CSV,
    CLIENTS,
    CANDIDATE_ROLES,
    JD_KEYWORDS,
    EMAIL_SENT_HISTORY_SCHEMA,
    init_database_files
)
from resume_customizer import customize_resume, extract_matched_jd_keywords

logger = logging.getLogger("gmail_sender")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def build_dynamic_hook(job_description: str) -> str:
    """
    Dynamic Hooking (Blueprint Section 5.2):
    Scans the job description against a pre-defined array of 60+ technology keywords (JD_KEYWORDS).
    Selects the top 3 matches and builds a contextual hook sentence:
    'My hands-on experience with Java, Spring Boot, and PostgreSQL maps directly to what you are looking for...'
    """
    matches = extract_matched_jd_keywords(job_description, max_keywords=3)
    if not matches:
        matches = ["enterprise architecture", "full-stack development", "cloud integration"]

    if len(matches) == 1:
        tech_str = matches[0]
    elif len(matches) == 2:
        tech_str = f"{matches[0]} and {matches[1]}"
    else:
        tech_str = f"{matches[0]}, {matches[1]}, and {matches[2]}"

    return f"My hands-on experience with {tech_str} maps directly to what you are looking for in this role."


def is_already_contacted(recruiter_email: str, candidate_key: str) -> bool:
    """
    De-duplicates candidate-specific outreach records against email_sent_history.csv.
    """
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
    if df.empty:
        return False

    clean_email = recruiter_email.strip().lower()
    matches = df[
        (df["recruiter_email"].str.lower() == clean_email) &
        (df["candidate"].str.lower() == candidate_key.lower()) &
        (df["email_sent_status"] == "sent")
    ]
    return len(matches) > 0


def record_sent_email(record: Dict[str, Any]) -> None:
    """Appends successful send record to email_sent_history.csv."""
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)

    row = {col: record.get(col, "") for col in EMAIL_SENT_HISTORY_SCHEMA}
    row_df = pd.DataFrame([row])
    df_combined = pd.concat([df, row_df], ignore_index=True)
    df_combined.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)


def update_recruiter_status(recruiter_email: str, status: str = "sent") -> None:
    """Updates email_sent_status in recruiters.csv."""
    init_database_files()
    df = pd.read_csv(RECRUITERS_CSV)
    mask = df["recruiter_email"].str.lower() == recruiter_email.strip().lower()
    df.loc[mask, "email_sent_status"] = status
    df.to_csv(RECRUITERS_CSV, index=False)


def get_smtp_connection(user_email: str, app_password: str, timeout: int = 15):
    """
    Secure SMTP Negotiation (Blueprint Section 5.2):
    Connects to smtp.gmail.com:587 with STARTTLS.
    If blocked or timed out, falls back to smtp.gmail.com:465 with SSL.
    Authenticates using .env app passwords.
    """
    # 1. Try Port 587 with STARTTLS
    try:
        logger.info("Connecting to smtp.gmail.com:587 with STARTTLS...")
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user_email, app_password)
        logger.info("Successfully established authenticated SMTP session on port 587.")
        return server
    except Exception as e_starttls:
        logger.warning(f"Port 587 STARTTLS connection failed: {e_starttls}. Falling back to port 465 SSL...")

    # 2. Fallback to Port 465 with SSL
    try:
        logger.info("Connecting to smtp.gmail.com:465 with SSL...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=timeout)
        server.ehlo()
        server.login(user_email, app_password)
        logger.info("Successfully established authenticated SMTP session on port 465.")
        return server
    except Exception as e_ssl:
        logger.error(f"Both port 587 and 465 SMTP negotiations failed: {e_ssl}")
        raise


def sanitize_filename(name: str) -> str:
    """Sanitizes non-ASCII characters to prevent 'noname' email attachment issues."""
    clean = re.sub(r"[^\x00-\x7F]+", "", name)
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", clean)
    return clean or "Resume.pdf"


def compose_email(
    candidate_key: str,
    recruiter_name: str,
    recruiter_email: str,
    job_description: str,
    target_role: str,
    pdf_attachment_path: Path
) -> Tuple[MIMEMultipart, str]:
    """
    MIME Composition:
    Builds personalized email with custom hook, CC/BCC, unique Message-ID,
    and sanitized randomized timestamped PDF attachment.
    """
    client = CLIENTS[candidate_key]
    candidate_name = client["name"]
    candidate_email = client["email"]
    candidate_phone = client.get("phone", "")
    candidate_location = client.get("location", "USA")
    work_auth = client.get("work_auth", "C2C")
    relocation = client.get("relocation", "Yes")
    rate = client.get("rate", "Open / Market Rate on C2C")

    team_lead_cc = os.getenv("TEAM_LEAD_CC_EMAIL", client.get("team_lead_cc", ""))
    admin_bcc = os.getenv("ADMIN_BCC_EMAIL", client.get("admin_bcc", ""))

    dynamic_hook = build_dynamic_hook(job_description)

    msg = MIMEMultipart()
    msg_id = make_msgid(domain="gmail.com")
    msg["Message-ID"] = msg_id
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = f"{candidate_name} <{candidate_email}>"
    msg["To"] = recruiter_email
    if team_lead_cc:
        msg["Cc"] = team_lead_cc
    if admin_bcc:
        msg["Bcc"] = admin_bcc

    subject = f"C2C Application: {candidate_name} - {target_role} ({candidate_location})"
    msg["Subject"] = subject

    # Plain text and HTML body
    body_text = f"""Hi {recruiter_name},

I came across your LinkedIn posting regarding the {target_role} position.

{dynamic_hook}

Here is a quick snapshot of my profile:
- Primary Domain: {target_role}
- Experience: {client.get('experience', '7+ Years')}
- Work Authorization: {work_auth}
- Current Location: {candidate_location}
- Relocation / Remote: {relocation}
- Availability: {client.get('availability', 'Immediate')}
- Contact: {candidate_phone} | {candidate_email}

I have attached my tailored resume for your review. Please let me know a convenient time for a brief discussion.

Best regards,
{candidate_name}
{candidate_phone}
{candidate_email}
"""

    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Attachment with randomized timestamped filename
    if pdf_attachment_path and pdf_attachment_path.exists():
        timestamp = int(time.time())
        clean_cand_name = sanitize_filename(candidate_name)
        attachment_filename = f"{clean_cand_name}_Resume_{timestamp}.pdf"

        with open(pdf_attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
            msg.attach(part)

    return msg, msg_id


def dispatch_outreach_email(
    candidate_key: str,
    recruiter_record: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Dispatches a single personalized cold outreach email for a recruiter lead.
    Enforces anti-throttling delay (3 seconds) and records history.
    """
    recruiter_email = recruiter_record.get("recruiter_email", "").strip()
    recruiter_name = recruiter_record.get("recruiter_name", "Recruiter").strip()
    role = recruiter_record.get("role") or CANDIDATE_ROLES[candidate_key]["primary_role"]
    jd_text = recruiter_record.get("job_description", "")
    post_url = recruiter_record.get("post_url", "")

    # Duplicate check
    if is_already_contacted(recruiter_email, candidate_key):
        logger.info(f"Skipping {recruiter_email}: Already contacted for candidate '{candidate_key}'.")
        return {"status": "skipped", "reason": "already_contacted"}

    logger.info(f"Customizing resume for candidate '{candidate_key}' against JD...")
    pdf_path, _ = customize_resume(candidate_key, jd_text, target_role=role)

    # Compose MIME
    msg, message_id = compose_email(
        candidate_key=candidate_key,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        job_description=jd_text,
        target_role=role,
        pdf_attachment_path=pdf_path
    )

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Anti-Throttling (Blueprint Section 5.2): 3-second sleep delay
    logger.info("Enforcing 3-second anti-throttling sleep delay...")
    time.sleep(3.0)

    is_dry_run = dry_run or os.getenv("DRY_RUN", "False").lower() in ["true", "1", "yes"]
    gmail_user = os.getenv("GMAIL_EMAIL", "")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")

    # If dummy or not configured, fall back to dry run
    if not gmail_user or "your_gmail" in gmail_user or not gmail_pwd or "abcd" in gmail_pwd:
        is_dry_run = True

    if is_dry_run:
        logger.info(f"[DRY-RUN / TEST MODE] Simulated email dispatched to: {recruiter_email}")
        logger.info(f"Subject: {msg['Subject']}")
        logger.info(f"Message-ID: {message_id}")

        history_record = {
            "recruiter_name": recruiter_name,
            "recruiter_email": recruiter_email,
            "role": role,
            "post_url": post_url,
            "candidate": candidate_key,
            "email_sent_status": "sent",
            "timestamp": now_str,
            "subject": msg["Subject"],
            "message_id": message_id,
            "followup_count": 0,
            "last_followup_at": "",
            "replied": 0
        }
        record_sent_email(history_record)
        update_recruiter_status(recruiter_email, "sent")
        return {"status": "sent", "mode": "dry_run", "message_id": message_id}

    # Live SMTP Dispatch
    server = None
    try:
        server = get_smtp_connection(gmail_user, gmail_pwd)
        all_recipients = [recruiter_email]
        if msg.get("Cc"):
            all_recipients.append(msg["Cc"])
        if msg.get("Bcc"):
            all_recipients.append(msg["Bcc"])

        server.sendmail(gmail_user, all_recipients, msg.as_string())
        logger.info(f"Successfully sent live email to {recruiter_email} (Msg ID: {message_id})")

        history_record = {
            "recruiter_name": recruiter_name,
            "recruiter_email": recruiter_email,
            "role": role,
            "post_url": post_url,
            "candidate": candidate_key,
            "email_sent_status": "sent",
            "timestamp": now_str,
            "subject": msg["Subject"],
            "message_id": message_id,
            "followup_count": 0,
            "last_followup_at": "",
            "replied": 0
        }
        record_sent_email(history_record)
        update_recruiter_status(recruiter_email, "sent")
        return {"status": "sent", "mode": "live", "message_id": message_id}

    except Exception as e:
        logger.error(f"Failed to dispatch email to {recruiter_email}: {e}")
        update_recruiter_status(recruiter_email, "failed")
        return {"status": "failed", "error": str(e)}
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


def batch_dispatch_pending(
    candidate_key: str,
    limit: int = 10,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Processes all eligible pending recruiters in recruiters.csv for the specified candidate.
    Returns (success_count, skipped_or_failed_count).
    """
    init_database_files()
    df = pd.read_csv(RECRUITERS_CSV)
    if df.empty:
        logger.info("No recruiter records found in recruiters.csv.")
        return 0, 0

    role_info = CANDIDATE_ROLES.get(candidate_key, {})
    primary_role = role_info.get("primary_role", "")

    # Match role or pending
    eligible = df[
        (df["email_sent_status"] == "pending") &
        (df["role"].str.lower().str.contains(primary_role.split()[0].lower()))
    ]

    if eligible.empty:
        eligible = df[df["email_sent_status"] == "pending"]

    logger.info(f"Identified {len(eligible)} pending recruiter leads for candidate '{candidate_key}'.")

    success_count = 0
    fail_count = 0

    for idx, row in eligible.head(limit).iterrows():
        res = dispatch_outreach_email(candidate_key, row.to_dict(), dry_run=dry_run)
        if res.get("status") == "sent":
            success_count += 1
        else:
            fail_count += 1

    return success_count, fail_count
