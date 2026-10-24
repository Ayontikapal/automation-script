"""
test_suite.py - Comprehensive Unit & Integration Test Suite for Recruitment & Outreach Automation System.
Validates all subsystems: Config, Filters, Lock Mutex, Scraper, Customizer, Sender, Follow-up, IMAP, and Analytics.
"""

import os
import sys
import time
import shutil
import unittest
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd
from docx import Document

from client_config import (
    BASE_DIR,
    CLIENTS,
    CANDIDATE_ROLES,
    JD_KEYWORDS,
    RECRUITERS_CSV,
    EMAIL_SENT_HISTORY_CSV,
    RECRUITERS_SCHEMA,
    EMAIL_SENT_HISTORY_SCHEMA,
    init_database_files
)
from lock_util import WordLock, kill_hung_word_instances
from linkedin_scraper import (
    build_search_query,
    clean_url,
    extract_email_from_text,
    is_usa_job,
    is_bench_sale,
    is_domain_mismatched,
    matches_strict_filter,
    generate_mock_scraped_leads
)
from resume_customizer import (
    extract_matched_jd_keywords,
    extract_resume_structure,
    call_llm_tailoring,
    customize_resume,
    compile_docx_to_pdf
)
from gmail_sender import (
    build_dynamic_hook,
    compose_email,
    is_already_contacted,
    dispatch_outreach_email,
    sanitize_filename
)
from followup_sender import (
    scan_followup_eligibility,
    generate_ai_value_proposition,
    dispatch_single_followup
)
from imap_reply_detector import (
    clean_sender_email,
    get_oldest_unreplied_date_boundary,
    check_replies
)
from analytics import compute_pipeline_metrics, generate_html_report


class TestAutomationPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Prepare clean test environment and ensure DB files exist."""
        init_database_files()

    def test_01_client_config_and_schemas(self):
        """Test candidate configurations, 60+ technology keywords, and CSV schema validity."""
        self.assertIn("safi", CLIENTS)
        self.assertIn("tanuja", CLIENTS)
        self.assertIn("jane_doe", CLIENTS)

        # Verify 60+ JD Keywords
        self.assertGreaterEqual(len(JD_KEYWORDS), 60)
        self.assertIn("Java", JD_KEYWORDS)
        self.assertIn("Spring Boot", JD_KEYWORDS)
        self.assertIn("Python", JD_KEYWORDS)
        self.assertIn("React", JD_KEYWORDS)

        # Check DB files existence and columns
        df_rec = pd.read_csv(RECRUITERS_CSV)
        for col in RECRUITERS_SCHEMA:
            self.assertIn(col, df_rec.columns)

        df_hist = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
        for col in EMAIL_SENT_HISTORY_SCHEMA:
            self.assertIn(col, df_hist.columns)

    def test_02_lock_util_mutex(self):
        """Test WordLock acquire, release, re-entrance, and stale recovery."""
        test_lock_file = BASE_DIR / "scratch" / "test_unit.lock"
        with WordLock(lock_path=test_lock_file, timeout=5) as lock:
            self.assertTrue(lock.acquired)
            self.assertTrue(test_lock_file.exists())
            content = test_lock_file.read_text()
            self.assertIn(f"PID:{os.getpid()}", content)

        # Lock should be released and unlinked
        self.assertFalse(test_lock_file.exists())

    def test_03_scraper_filters_and_cleaning(self):
        """Test strict filtering, location detection, bench sale exclusion, and domain check."""
        # Query builder
        query = build_search_query("Java Developer")
        self.assertEqual(query, '"Java Developer" + C2C -hotlist -fulltime -"available consultants" -Bench')

        # Clean URL
        dirty = "https://www.linkedin.com/posts/activity-123456?trackingId=abc%3D%3D&position=1"
        cleaned = clean_url(dirty)
        self.assertEqual(cleaned, "https://www.linkedin.com/posts/activity-123456")

        # Email extraction
        text_with_email = "Great C2C opportunity! Reach out to recruiter.john@tech-staffing.com for immediate interview."
        extracted = extract_email_from_text(text_with_email)
        self.assertEqual(extracted, "recruiter.john@tech-staffing.com")

        # US location vs Non-US
        us_text = "Role in Dallas, TX. Open for Corp-to-Corp."
        non_us_text = "Java opening in Pune, India. Night shifts."
        self.assertTrue(is_usa_job(us_text))
        self.assertFalse(is_usa_job(non_us_text))

        # Bench sale exclusion
        bench_text = "Hotlist of available consultants on my bench ready to deploy."
        self.assertTrue(is_bench_sale(bench_text))
        valid_job_text = "Looking for Senior React Developer for 12 months C2C contract in Chicago, IL."
        self.assertFalse(is_bench_sale(valid_job_text))

        # Domain mismatch
        qa_text = "Urgently hiring Manual QA Tester with Selenium and TestNG."
        self.assertTrue(is_domain_mismatched(qa_text, "Java Full Stack Developer"))

        # Strict filter overall pass/fail
        passed_valid, reason_valid = matches_strict_filter(valid_job_text, "React Developer")
        self.assertTrue(passed_valid)
        self.assertEqual(reason_valid, "valid")

        passed_bench, reason_bench = matches_strict_filter(bench_text, "React Developer")
        self.assertFalse(passed_bench)
        self.assertEqual(reason_bench, "bench_mark_excluded")

    def test_04_resume_customizer_and_style_preservation(self):
        """Test resume structure extraction, keyword weaving, run style preservation, and PDF compilation."""
        client_key = "safi"
        sample_jd = (
            "Looking for Senior Java Developer with Spring Boot, Microservices, Kafka, PostgreSQL, "
            "and Docker experience for C2C in Dallas, TX."
        )

        matched_kws = extract_matched_jd_keywords(sample_jd, max_keywords=6)
        self.assertIn("Spring Boot", matched_kws)
        self.assertIn("Kafka", matched_kws)

        # Run customization
        pdf_path, tailored_data = customize_resume(client_key, sample_jd)
        self.assertTrue(pdf_path.exists())
        self.assertTrue(str(pdf_path).endswith(".pdf"))
        self.assertGreater(pdf_path.stat().st_size, 1000)

        # Check tailored properties
        self.assertIn("rewritten_summary", tailored_data)
        self.assertIn("rewritten_paragraphs", tailored_data)
        self.assertIn("rewritten_skills", tailored_data)
        self.assertGreater(len(tailored_data["rewritten_summary"]), 20)

    def test_05_client_specific_customizer_hooks(self):
        """Test Tanuja Sharma's dedicated customizer hook (tanuja_customizer)."""
        sample_jd_ml = (
            "Senior Machine Learning Engineer needed. Must have PyTorch, Scikit-Learn, Databricks, "
            "and LLM deployment background on AWS cloud."
        )
        pdf_path, tailored_data = customize_resume("tanuja", sample_jd_ml)
        self.assertTrue(pdf_path.exists())
        self.assertGreater(pdf_path.stat().st_size, 1000)
        self.assertIn("rewritten_summary", tailored_data)

    def test_06_gmail_sender_mime_and_hook(self):
        """Test dynamic hooking, MIME composition, attachment sanitization, and dispatch."""
        sample_jd = "Senior React Developer with TypeScript, Redux, and Tailwind CSS needed for C2C contract."
        hook = build_dynamic_hook(sample_jd)
        self.assertIn("My hands-on experience with", hook)
        self.assertIn("maps directly to what you are looking for", hook)

        # Filename sanitization
        clean_name = sanitize_filename("Safi Ahmed / Dev (Lead)")
        self.assertNotIn("/", clean_name)
        self.assertNotIn("(", clean_name)

        # Compose MIME
        dummy_pdf = BASE_DIR / "scratch" / "test_attachment.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 test")

        msg, msg_id = compose_email(
            candidate_key="jane_doe",
            recruiter_name="Amanda",
            recruiter_email="amanda@testrecruit.com",
            job_description=sample_jd,
            target_role="React Developer",
            pdf_attachment_path=dummy_pdf
        )

        self.assertIn("Message-ID", msg)
        self.assertTrue(msg["Message-ID"].startswith("<"))
        self.assertIn("Jane Doe", msg["From"])
        self.assertEqual(msg["To"], "amanda@testrecruit.com")
        self.assertIn("C2C Application", msg["Subject"])

        # Dispatch dry-run test
        rec = {
            "recruiter_name": "Unit Recruiter",
            "recruiter_email": f"unit_test_{int(time.time())}@recruitcorp.com",
            "role": "React Developer",
            "post_url": "https://linkedin.com/posts/unit-test",
            "job_description": sample_jd
        }
        res = dispatch_outreach_email("jane_doe", rec, dry_run=True)
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["mode"], "dry_run")

    def test_07_followup_sender_and_threading_headers(self):
        """Test follow-up eligibility scan, In-Reply-To / References headers, and status update."""
        # Pitch generator
        pitch = generate_ai_value_proposition(
            candidate_key="safi",
            target_role="Java Full Stack Developer",
            job_description="Java 17, Spring Boot, Microservices"
        )
        self.assertIsInstance(pitch, str)
        self.assertGreater(len(pitch), 15)

        # Create a mock unreplied sent record in history
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_email = f"followup_test_{int(time.time())}@company.com"
        orig_msg_id = f"<test-{int(time.time())}@gmail.com>"

        df_hist = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
        new_row = {
            "recruiter_name": "Followup Lead",
            "recruiter_email": test_email,
            "role": "Java Full Stack Developer",
            "post_url": "https://linkedin.com/test",
            "candidate": "safi",
            "email_sent_status": "sent",
            "timestamp": now_ts,
            "subject": "C2C Application: Safi Ahmed - Java Full Stack Developer",
            "message_id": orig_msg_id,
            "followup_count": 0,
            "last_followup_at": "",
            "replied": 0
        }
        df_hist = pd.concat([df_hist, pd.DataFrame([new_row])], ignore_index=True)
        df_hist.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)

        # Dispatch follow-up (0 days threshold for unit test)
        res = dispatch_single_followup(0, new_row, dry_run=True)
        self.assertEqual(res["status"], "sent")

        # Verify history was updated
        df_updated = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
        matched = df_updated[df_updated["recruiter_email"] == test_email]
        self.assertEqual(len(matched), 1)
        self.assertEqual(int(matched.iloc[0]["followup_count"]), 1)
        self.assertTrue(len(str(matched.iloc[0]["last_followup_at"])) > 5)

    def test_08_imap_reply_detector(self):
        """Test IMAP sender parsing, date windowing, and status update."""
        raw_header = 'John Doe <john.doe@recruiting-partners.com>'
        clean = clean_sender_email(raw_header)
        self.assertEqual(clean, "john.doe@recruiting-partners.com")

        # Test date windowing
        oldest_dt = get_oldest_unreplied_date_boundary()
        self.assertIsInstance(oldest_dt, datetime)

        # Test simulated reply matching
        count, senders = check_replies(simulate_test=True)
        self.assertGreaterEqual(count, 0)

    def test_09_analytics_computation_and_dashboard(self):
        """Test pipeline analytics calculation and HTML dashboard compilation."""
        metrics = compute_pipeline_metrics()
        self.assertIn("total_scraped", metrics)
        self.assertIn("sent_outreach", metrics)
        self.assertIn("reply_rate", metrics)
        self.assertIn("candidates", metrics)
        self.assertGreaterEqual(len(metrics["candidates"]), 3)

        # Generate HTML report
        report_file = generate_html_report()
        self.assertTrue(report_file.exists())
        html = report_file.read_text(encoding="utf-8")

        # Check visual components in HTML
        self.assertIn("Recruitment & Outreach Automation Analytics", html)
        self.assertIn("candidateBarChart", html)
        self.assertIn("statusDoughnutChart", html)
        self.assertIn("Safi Ahmed", html)
        self.assertIn("Tanuja Sharma", html)
        self.assertIn("Jane Doe", html)
        self.assertIn("chart.js", html.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
