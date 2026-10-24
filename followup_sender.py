"""
followup_sender.py - Threaded follow-up dispatch engine for unanswered outreach.
Configures In-Reply-To and References headers, prepends 'Re: ', generates an AI
value proposition, re-attaches candidate resume, and coordinates SMTP delivery.
"""

import os
import re
import sys
import time
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import make_msgid, formatdate
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
import requests

load_dotenv()

from client_config import (
    BASE_DIR,
    EMAIL_SENT_HISTORY_CSV,
    CLIENTS,
    CANDIDATE_ROLES,
    init_database_files
)
from gmail_sender import get_smtp_connection, sanitize_filename
from resume_customizer import customize_resume

logger = logging.getLogger("followup_sender")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def generate_ai_value_proposition(
    candidate_key: str,
    target_role: str,
    job_description: str
) -> str:
    """
    AI Value Proposition (Blueprint Section 5.4):
    Uses OpenRouter / Gemini / Groq / Fallback to generate a concise, 1-to-2 sentence
    value proposition linking the client's core skills directly with the recruiter's job description.
    """
    client = CLIENTS.get(candidate_key, {})
    name = client.get("name", "Candidate")
    summary = client.get("summary", "")

    prompt = (
        f"Generate a concise 1-to-2 sentence professional value proposition linking {name}'s core skills "
        f"directly with this contract requirement for {target_role}. Keep it polite, impactful, and direct.\n"
        f"Candidate Background: {summary}\n"
        f"Job Description Snippet: {job_description[:600]}\n"
        f"Output ONLY the 1-2 sentence pitch without quotes or meta-text."
    )

    # 1. Try OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key and "yourOpenRouter" not in openrouter_key:
        try:
            model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4},
                timeout=15
            )
            if res.status_code == 200:
                pitch = res.json()["choices"][0]["message"]["content"].strip()
                if pitch:
                    return pitch
        except Exception as e:
            logger.debug(f"OpenRouter pitch generation failed: {e}")

    # 2. Try Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key and "YourGeminiApiKey" not in gemini_key:
        try:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.status_code == 200:
                pitch = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if pitch:
                    return pitch
        except Exception as e:
            logger.debug(f"Gemini pitch generation failed: {e}")

    # Fallback Pitch
    return (
        f"With deep expertise in {target_role} and enterprise production architectures, "
        f"I can quickly hit the ground running on day one to accelerate your project milestones on C2C."
    )


def scan_followup_eligibility(days_threshold: int = 7) -> pd.DataFrame:
    """
    Eligibility Scan (Blueprint Section 5.4):
    Filters email_sent_history.csv for records matching:
    email_sent_status == 'sent', followup_count == 0, replied == 0,
    and sent >= days_threshold days ago.
    """
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
    if df.empty:
        return df

    # Enforce type safety
    df["followup_count"] = pd.to_numeric(df["followup_count"], errors="coerce").fillna(0).astype(int)
    df["replied"] = pd.to_numeric(df["replied"], errors="coerce").fillna(0).astype(int)

    # Date filtering
    eligible_indices = []
    now = datetime.now()

    for idx, row in df.iterrows():
        if row.get("email_sent_status") != "sent":
            continue
        if row.get("followup_count") > 0:
            continue
        if row.get("replied") == 1:
            continue

        ts_str = str(row.get("timestamp", ""))
        try:
            sent_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            elapsed_days = (now - sent_dt).total_seconds() / 86400.0
            if elapsed_days >= days_threshold:
                eligible_indices.append(idx)
        except Exception:
            # If timestamp parsing fails or zero days threshold test
            if days_threshold == 0:
                eligible_indices.append(idx)

    return df.loc[eligible_indices]


def dispatch_single_followup(
    history_row_idx: int,
    history_row: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Dispatches a threaded follow-up email linked to the original Message-ID.
    """
    recruiter_name = history_row.get("recruiter_name", "Recruiter")
    recruiter_email = history_row.get("recruiter_email", "")
    role = history_row.get("role", "Software Engineer")
    candidate_key = history_row.get("candidate", "safi")
    orig_msg_id = history_row.get("message_id", "")
    orig_subject = history_row.get("subject", f"C2C Application: {role}")
    post_url = history_row.get("post_url", "")

    client = CLIENTS.get(candidate_key, CLIENTS["safi"])
    candidate_name = client["name"]
    candidate_email = client["email"]
    candidate_phone = client.get("phone", "")

    # Thread Linkage: Prepend "Re: " to subject
    subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

    # AI Value Proposition
    value_prop = generate_ai_value_proposition(
        candidate_key=candidate_key,
        target_role=role,
        job_description=f"Role: {role}. Contract position on C2C."
    )

    msg = MIMEMultipart()
    new_msg_id = make_msgid(domain="gmail.com")
    msg["Message-ID"] = new_msg_id
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = f"{candidate_name} <{candidate_email}>"
    msg["To"] = recruiter_email

    team_lead_cc = os.getenv("TEAM_LEAD_CC_EMAIL", client.get("team_lead_cc", ""))
    admin_bcc = os.getenv("ADMIN_BCC_EMAIL", client.get("admin_bcc", ""))
    if team_lead_cc:
        msg["Cc"] = team_lead_cc
    if admin_bcc:
        msg["Bcc"] = admin_bcc

    msg["Subject"] = subject

    # Thread Linkage RFC headers (Section 5.4)
    if orig_msg_id:
        msg["In-Reply-To"] = orig_msg_id
        msg["References"] = orig_msg_id

    body = f"""Hi {recruiter_name},

Following up on my previous outreach regarding the {role} position.

{value_prop}

I remain immediately available for C2C contract engagements and would welcome the opportunity to discuss how my technical background aligns with your project objectives.

I have re-attached my resume for your reference.

Best regards,
{candidate_name}
{candidate_phone}
{candidate_email}
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Re-attach resume
    try:
        pdf_path, _ = customize_resume(candidate_key, f"Target role: {role}")
        if pdf_path.exists():
            clean_name = sanitize_filename(candidate_name)
            filename = f"{clean_name}_Resume_{int(time.time())}.pdf"
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)
    except Exception as e:
        logger.warning(f"Could not attach fresh resume for follow-up: {e}")

    # Anti-throttling
    time.sleep(3.0)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_dry_run = dry_run or os.getenv("DRY_RUN", "False").lower() in ["true", "1", "yes"]
    gmail_user = os.getenv("GMAIL_EMAIL", "")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")

    if not gmail_user or "your_gmail" in gmail_user or not gmail_pwd or "abcd" in gmail_pwd:
        is_dry_run = True

    if is_dry_run:
        logger.info(f"[DRY-RUN] Dispatched threaded follow-up to {recruiter_email}")
        logger.info(f"Subject: {msg['Subject']} | In-Reply-To: {orig_msg_id}")
        _update_history_after_followup(recruiter_email, candidate_key, now_str)
        return {"status": "sent", "mode": "dry_run", "recruiter_email": recruiter_email}

    # Live SMTP send
    server = None
    try:
        server = get_smtp_connection(gmail_user, gmail_pwd)
        recipients = [recruiter_email]
        if team_lead_cc:
            recipients.append(team_lead_cc)
        if admin_bcc:
            recipients.append(admin_bcc)

        server.sendmail(gmail_user, recipients, msg.as_string())
        logger.info(f"Live follow-up delivered to {recruiter_email}")
        _update_history_after_followup(recruiter_email, candidate_key, now_str)
        return {"status": "sent", "mode": "live", "recruiter_email": recruiter_email}
    except Exception as e:
        logger.error(f"Follow-up send failed for {recruiter_email}: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


def _update_history_after_followup(recruiter_email: str, candidate_key: str, timestamp_str: str):
    """Updates followup_count and last_followup_at in email_sent_history.csv."""
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
    
    # Coerce columns to flexible object/int types
    if "last_followup_at" not in df.columns:
        df["last_followup_at"] = ""
    df["last_followup_at"] = df["last_followup_at"].astype("object")
    
    if "followup_count" not in df.columns:
        df["followup_count"] = 0
    df["followup_count"] = pd.to_numeric(df["followup_count"], errors="coerce").fillna(0).astype(int)

    mask = (
        (df["recruiter_email"].fillna("").astype(str).str.lower() == recruiter_email.strip().lower()) &
        (df["candidate"].fillna("").astype(str).str.lower() == candidate_key.lower())
    )
    df.loc[mask, "followup_count"] = 1
    df.loc[mask, "last_followup_at"] = str(timestamp_str)
    df.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)


def run_followup_pipeline(days_threshold: int = 7, dry_run: bool = False) -> int:
    """
    Executes the full follow-up pipeline across all candidates.
    Returns count of sent follow-ups.
    """
    eligible_df = scan_followup_eligibility(days_threshold=days_threshold)
    if eligible_df.empty:
        logger.info(f"No candidates eligible for follow-up (unanswered >= {days_threshold} days).")
        return 0

    logger.info(f"Found {len(eligible_df)} eligible records for follow-up outreach.")
    sent_count = 0
    for idx, row in eligible_df.iterrows():
        res = dispatch_single_followup(idx, row.to_dict(), dry_run=dry_run)
        if res.get("status") == "sent":
            sent_count += 1

    logger.info(f"Completed follow-up batch: {sent_count} follow-ups dispatched.")
    return sent_count
