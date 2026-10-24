"""
imap_reply_detector.py - Scans Gmail inbox for recruiter replies using secure IMAP.
Features date windowing based on oldest unreplied outreach, read-only INBOX inspection,
batch header fetching (100 msgs), sender address extraction, and database status updating.
"""

import os
import re
import sys
import time
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from client_config import (
    BASE_DIR,
    EMAIL_SENT_HISTORY_CSV,
    init_database_files
)

logger = logging.getLogger("imap_reply_detector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_oldest_unreplied_date_boundary(default_days: int = 30) -> datetime:
    """
    Date Windowing (Blueprint Section 5.5):
    Analyzes email_sent_history.csv to find the timestamp of the oldest unreplied sent email.
    Sets this as the search boundary (defaulting to 30 days if empty) to optimize sync speeds.
    """
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)

    fallback_date = datetime.now() - timedelta(days=default_days)
    if df.empty:
        return fallback_date

    unreplied = df[(df["email_sent_status"] == "sent") & (df["replied"] == 0)]
    if unreplied.empty:
        return fallback_date

    oldest_dt = None
    for ts in unreplied["timestamp"].dropna():
        try:
            dt = datetime.strptime(str(ts).strip(), "%Y-%m-%d %H:%M:%S")
            if oldest_dt is None or dt < oldest_dt:
                oldest_dt = dt
        except Exception:
            pass

    return oldest_dt or fallback_date


def clean_sender_email(raw_from: str) -> str:
    """Extracts clean lowercase email address from From header string."""
    match = re.search(r"<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>", raw_from)
    if match:
        return match.group(1).lower().strip()
    match2 = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw_from)
    if match2:
        return match2.group(0).lower().strip()
    return ""


def check_replies(batch_size: int = 100, simulate_test: bool = False) -> Tuple[int, List[str]]:
    """
    Executes the IMAP Reply Detection Pipeline (Section 5.5).
    Connects to imap.gmail.com:993 with SSL, selects INBOX in read-only mode,
    searches SINCE DD-Mon-YYYY, fetches headers in batches of 100,
    and updates matched recruiters with replied = 1.
    """
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
    if df.empty:
        logger.info("No sent outreach records in email_sent_history.csv to monitor.")
        return 0, []

    # Map of pending recruiter emails awaiting reply
    unreplied_mask = (df["email_sent_status"] == "sent") & (df["replied"] == 0)
    pending_emails: Set[str] = set(df.loc[unreplied_mask, "recruiter_email"].dropna().str.lower().str.strip())

    if not pending_emails:
        logger.info("No unreplied outreach records currently pending reply.")
        return 0, []

    logger.info(f"Monitoring replies for {len(pending_emails)} unreplied outreach contacts...")

    # Date boundary
    boundary_dt = get_oldest_unreplied_date_boundary()
    since_date_str = boundary_dt.strftime("%d-%b-%Y")
    logger.info(f"IMAP search date window: SINCE {since_date_str}")

    gmail_user = os.getenv("GMAIL_EMAIL", "")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")

    matched_senders: List[str] = []

    # Check credentials
    if simulate_test or not gmail_user or "your_gmail" in gmail_user or not gmail_pwd or "abcd" in gmail_pwd:
        logger.info("[SIMULATION / TEST MODE] Running simulated reply detector check.")
        # If test mode, check if any pending emails exist and simulate a match for testing
        test_match = list(pending_emails)[0] if pending_emails else "recruiter@example.com"
        logger.info(f"[SIMULATION] Mock detected reply from recruiter: {test_match}")
        matched_senders.append(test_match)
        _update_replied_status(matched_senders)
        return len(matched_senders), matched_senders

    mail = None
    try:
        # Secure IMAP Connection (port 993 SSL)
        logger.info("Connecting to imap.gmail.com:993 via SSL...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_user, gmail_pwd)

        # Select INBOX in read-only mode
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            logger.error("Failed to select INBOX in read-only mode.")
            return 0, []

        # Search Query: SINCE DD-Mon-YYYY
        search_criteria = f'(SINCE "{since_date_str}")'
        status, data = mail.search(None, search_criteria)
        if status != "OK" or not data[0]:
            logger.info("No incoming emails found within the search date window.")
            return 0, []

        msg_ids = data[0].split()
        total_msgs = len(msg_ids)
        logger.info(f"Found {total_msgs} messages in date window. Processing in batches of {batch_size}...")

        # Batch Processing in batches of 100
        for i in range(0, total_msgs, batch_size):
            chunk = msg_ids[i:i + batch_size]
            id_sequence = b",".join(chunk).decode("ascii")

            # Fetch headers only to minimize bandwidth
            res, fetch_data = mail.fetch(id_sequence, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE IN-REPLY-TO)])")
            if res != "OK":
                continue

            for response_part in fetch_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    sender_raw = msg.get("From", "")
                    sender_clean = clean_sender_email(sender_raw)

                    if sender_clean and sender_clean in pending_emails:
                        if sender_clean not in matched_senders:
                            logger.info(f"MATCH DETECTED: Incoming reply received from recruiter: {sender_clean}")
                            matched_senders.append(sender_clean)

        if matched_senders:
            _update_replied_status(matched_senders)

        logger.info(f"Reply scan completed. {len(matched_senders)} new replies matched and recorded.")
        return len(matched_senders), matched_senders

    except Exception as e:
        logger.error(f"IMAP reply detection error: {e}")
        return 0, []
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass


def _update_replied_status(matched_emails: List[str]):
    """Sets replied = 1 for matched recruiter emails in email_sent_history.csv."""
    init_database_files()
    df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
    clean_matched = {e.lower().strip() for e in matched_emails}

    if "recruiter_email" in df.columns:
        mask = df["recruiter_email"].fillna("").astype(str).str.lower().isin(clean_matched)
        df.loc[mask, "replied"] = 1
        df.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)
        logger.info(f"Updated replied=1 for {mask.sum()} entries in {EMAIL_SENT_HISTORY_CSV}")


if __name__ == "__main__":
    count, senders = check_replies(simulate_test=True)
    print(f"Reply sync completed: {count} replies detected: {senders}")
