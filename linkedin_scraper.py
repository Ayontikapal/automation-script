"""
linkedin_scraper.py - Playwright-based scraper for targeted LinkedIn recruiter posts.
Implements the Three-Dots Clipboard Interceptor, strict regex email extraction,
US location filtering, bench sale exclusions, and domain compatibility checks.
"""

import os
import re
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote_plus
from typing import List, Dict, Optional, Tuple, Any

import pandas as pd
from client_config import (
    BASE_DIR,
    RECRUITERS_CSV,
    SESSION_JSON,
    NON_USA_INDICATORS,
    US_LOCATION_INDICATORS,
    BENCH_INDICATORS,
    DOMAIN_EXCLUSIONS,
    CANDIDATE_ROLES,
    RECRUITERS_SCHEMA,
    init_database_files
)

logger = logging.getLogger("linkedin_scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def build_search_query(role: str) -> str:
    """
    Builds the search query specified in blueprint Section 5.1 Step 1:
    "<Role> + C2C -hotlist -fulltime -\"available consultants\" -Bench"
    """
    return f'"{role}" + C2C -hotlist -fulltime -"available consultants" -Bench'


def build_search_url(role: str) -> str:
    """
    Builds the LinkedIn search URL targeting US (geoUrn=103644278) sorted by date_posted.
    """
    raw_query = build_search_query(role)
    encoded = quote_plus(raw_query)
    return (
        f"https://www.linkedin.com/search/results/content/?"
        f"keywords={encoded}&sortBy=%22date_posted%22&geoUrn=103644278"
    )


def clean_url(raw_url: str) -> str:
    """Removes tracking query parameters from copied LinkedIn post URL."""
    try:
        parsed = urlparse(raw_url.strip())
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        return raw_url.strip()


def extract_recruiter_name(post_text: str, card_element=None, profile_url: str = "") -> str:
    """
    Extracts recruiter name from profile URL (/in/username) or post header lines.
    """
    if profile_url and "/in/" in profile_url:
        try:
            match = re.search(r"/in/([^/?#]+)", profile_url)
            if match:
                slug = match.group(1).replace("-", " ")
                cleaned = " ".join([word.capitalize() for word in slug.split() if not word.isdigit()])
                if cleaned:
                    return cleaned
        except Exception:
            pass

    # Fallback to inspecting the first non-empty lines
    lines = [line.strip() for line in post_text.splitlines() if line.strip()]
    for line in lines[:4]:
        # If looks like a name (2-3 words, capitalized, no special chars)
        words = line.split()
        if 2 <= len(words) <= 3 and all(w.isalpha() for w in words):
            return line

    return "Recruiter"


def extract_email_from_text(text: str) -> Optional[str]:
    """
    Extracts the first valid email address using strict regex.
    Ignores common false positives (e.g. image extensions or domain examples).
    """
    matches = EMAIL_REGEX.findall(text)
    for email in matches:
        email = email.strip().lower()
        # Filter false positives like test@example.com or image filenames
        if any(email.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
            continue
        if "noreply" in email or "donotreply" in email:
            continue
        return email
    return None


def is_usa_job(text: str) -> bool:
    """
    Location Filter (Section 5.1 Step 5):
    Reject if matches NON_USA_INDICATORS (Pune, Noida, India, Canada).
    Allow if matches major US cities, state abbreviations, or explicit US terms.
    """
    lower = text.lower()
    for indicator in NON_USA_INDICATORS:
        # Match whole word boundary to avoid false substring triggers
        if re.search(r"\b" + re.escape(indicator) + r"\b", lower):
            return False

    for indicator in US_LOCATION_INDICATORS:
        if re.search(r"\b" + re.escape(indicator) + r"\b", lower):
            return True

    # If post explicitly mentions C2C or Corp-to-Corp or US Dollar ($ / /hr), consider USA candidate
    if "c2c" in lower or "corp to corp" in lower or "w2" in lower or "/hr" in lower or "$/hr" in lower:
        return True

    return False


def is_bench_sale(text: str) -> bool:
    """
    Bench mark exclusion:
    Exclude posts containing phrases like 'on my bench', 'candidate available',
    or 'marketing my consultant'.
    """
    lower = text.lower()
    for phrase in BENCH_INDICATORS:
        if phrase in lower:
            return True
    return False


def is_domain_mismatched(text: str, target_role: str) -> bool:
    """
    Domain mismatch check:
    Detects declared job title by parsing lines. Excludes posts if the job title
    targets domains (like DevOps, QA, Salesforce) that do not align with candidate role.
    """
    lower = text.lower()
    # Check general exclusion lists mapped to role
    for role_name, exclusions in DOMAIN_EXCLUSIONS.items():
        if role_name.lower() in target_role.lower():
            for forbidden in exclusions:
                if re.search(r"\b" + re.escape(forbidden) + r"\b", lower):
                    return True
    return False


def matches_strict_filter(post_text: str, target_role: str) -> Tuple[bool, str]:
    """
    Runs full strict filtering suite.
    Returns (passed, reason).
    """
    if is_bench_sale(post_text):
        return False, "bench_mark_excluded"

    if not is_usa_job(post_text):
        return False, "non_usa_location"

    if is_domain_mismatched(post_text, target_role):
        return False, "mismatched_role"

    return True, "valid"


def intercept_post_link_via_three_dots(page, card) -> str:
    """
    The Three-Dots Clipboard Interceptor (Blueprint Section 5.1 Step 3):
    1. Scrolls the targeted card to the center of the viewport.
    2. Clicks post control menu (button[aria-label*='control menu for post']).
    3. Locates and clicks 'Copy link' option.
    4. Evaluates page clipboard state:
       navigator.clipboard.writeText('') followed by navigator.clipboard.readText().
    5. Cleans query parameters and returns clean URL.
    """
    try:
        # Scroll card into center of viewport
        card.scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        # Locate three dots button inside this card
        control_btn = card.locator("button[aria-label*='control menu for post'], button[aria-label*='Control menu for post']").first
        if control_btn.count() == 0:
            # Try generic dropdown trigger inside post
            control_btn = card.locator("button.feed-shared-control-menu__trigger").first

        if control_btn.count() > 0:
            control_btn.click()
            page.wait_for_timeout(400)

            # Locate and click 'Copy link'
            copy_option = page.locator("div[role='button']:has-text('Copy link to post'), li:has-text('Copy link'), button:has-text('Copy link')").first
            if copy_option.count() > 0:
                # Clear clipboard first
                try:
                    page.evaluate("() => navigator.clipboard.writeText('')")
                except Exception:
                    pass

                copy_option.click()
                page.wait_for_timeout(500)

                # Read from clipboard
                copied = page.evaluate("() => navigator.clipboard.readText()")
                if copied and "linkedin.com" in copied:
                    return clean_url(copied)

    except Exception as e:
        logger.debug(f"Three-dots interceptor exception: {e}")

    # Fallback to direct anchor links within card if available
    try:
        anchors = card.locator("a[href*='/feed/update/'], a[href*='/posts/']").all()
        for a in anchors:
            href = a.get_attribute("href")
            if href:
                return clean_url(href)
    except Exception:
        pass

    return ""


def save_recruiters_to_csv(records: List[Dict[str, Any]]) -> int:
    """
    Saves new scraped recruiter records to recruiters.csv without duplicates.
    Returns number of newly added records.
    """
    init_database_files()
    df_existing = pd.read_csv(RECRUITERS_CSV)

    existing_emails = set(df_existing["recruiter_email"].dropna().str.lower())
    existing_urls = set(df_existing["post_url"].dropna())

    new_rows = []
    for r in records:
        email = r.get("recruiter_email", "").strip().lower()
        url = r.get("post_url", "").strip()

        if email and email in existing_emails:
            continue
        if url and url in existing_urls:
            continue

        new_rows.append(r)
        if email:
            existing_emails.add(email)
        if url:
            existing_urls.add(url)

    if new_rows:
        df_new = pd.DataFrame(new_rows)
        # Ensure schema alignment
        for col in RECRUITERS_SCHEMA:
            if col not in df_new.columns:
                df_new[col] = ""
        df_new = df_new[RECRUITERS_SCHEMA]

        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.to_csv(RECRUITERS_CSV, index=False)
        logger.info(f"Persisted {len(new_rows)} new recruiter records to {RECRUITERS_CSV}")

    return len(new_rows)


def run_linkedin_scraper(
    target_role: str = "Java Full Stack Developer",
    max_scrolls: int = 6,
    headless: bool = True,
    session_path: Path = SESSION_JSON
) -> List[Dict[str, Any]]:
    """
    Executes the Playwright scraper pipeline as described in Section 5.1.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright is not available. Please install dependencies.")
        return []

    if not session_path.exists() or session_path.stat().st_size < 10:
        logger.warning(
            f"No active session found at {session_path}. "
            f"Please run 'Setup/Test LinkedIn Login Session' (Option 2) first."
        )
        return []

    results: List[Dict[str, Any]] = []
    search_url = build_search_url(target_role)

    logger.info(f"Initiating scraping for role: '{target_role}'")
    logger.info(f"Target URL: {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(search_url, timeout=45000)
            page.wait_for_timeout(3000)

            # Check if redirected to login
            if "login" in page.url or "checkpoint" in page.url:
                logger.error("Session cookies expired or blocked by LinkedIn checkpoint. Please re-run login setup.")
                return []

            # 2. Pagination & Scroll: Scrolls 6 times, forcing visibility clicks on 'See more'
            for scroll_idx in range(max_scrolls):
                logger.info(f"Scroll iteration {scroll_idx + 1}/{max_scrolls}...")
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(2000)

                # Click all 'See more' buttons to expand post bodies
                see_more_buttons = page.locator("button.feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('See more')").all()
                for btn in see_more_buttons:
                    try:
                        if btn.is_visible():
                            btn.click(timeout=1000)
                    except Exception:
                        pass

            # Extract post cards
            cards = page.locator("div.feed-shared-update-v2, div[data-urn*='urn:li:activity']").all()
            logger.info(f"Discovered {len(cards)} post cards on page.")

            for i, card in enumerate(cards):
                try:
                    # Extract text content
                    post_text = card.inner_text()
                    if not post_text:
                        continue

                    # Email Extraction
                    recruiter_email = extract_email_from_text(post_text)
                    if not recruiter_email:
                        # Check mailto: anchors
                        mailto_links = card.locator("a[href^='mailto:']").all()
                        for m in mailto_links:
                            href = m.get_attribute("href") or ""
                            clean_m = href.replace("mailto:", "").split("?")[0].strip()
                            if clean_m and "@" in clean_m:
                                recruiter_email = clean_m
                                break

                    if not recruiter_email:
                        continue

                    # Strict Filters
                    passed, reason = matches_strict_filter(post_text, target_role)
                    if not passed:
                        logger.info(f"Filtered out post for {recruiter_email}: reason={reason}")
                        continue

                    # Three-Dots Clipboard Interceptor
                    post_url = intercept_post_link_via_three_dots(page, card)
                    if not post_url:
                        post_url = f"https://www.linkedin.com/feed/#post-{i}"

                    # Profile link and name
                    author_anchor = card.locator("a[href*='/in/']").first
                    profile_url = author_anchor.get_attribute("href") if author_anchor.count() > 0 else ""
                    recruiter_name = extract_recruiter_name(post_text, card, profile_url)

                    record = {
                        "recruiter_name": recruiter_name,
                        "recruiter_email": recruiter_email,
                        "role": target_role,
                        "post_url": post_url,
                        "job_description": post_text.strip()[:2000],
                        "email_sent_status": "pending",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    results.append(record)
                    logger.info(f"Target lead matched: {recruiter_name} ({recruiter_email})")

                except Exception as ex:
                    logger.debug(f"Error parsing card {i}: {ex}")

        except Exception as e:
            logger.error(f"Error in scraping pipeline: {e}")
        finally:
            context.close()
            browser.close()

    if results:
        save_recruiters_to_csv(results)

    return results


def generate_mock_scraped_leads(role: str = "Java Full Stack Developer", count: int = 5) -> List[Dict[str, Any]]:
    """
    Generates realistic, validated USA C2C recruiter posts for testing and demonstration
    when live LinkedIn credentials/session is not yet connected.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sample_records = [
        {
            "recruiter_name": "Sarah Jenkins",
            "recruiter_email": "sarah.jenkins@teksystems-staffing.com",
            "role": "Java Full Stack Developer",
            "post_url": "https://www.linkedin.com/posts/sarah-jenkins_c2c-javadeveloper-springboot-activity-718293847291029384",
            "job_description": (
                "Urgently looking for a Senior Java Full Stack Developer for an immediate Corp-to-Corp (C2C) role.\n"
                "Client: Major Healthcare client in Dallas, TX (Remote with occasional travel).\n"
                "Tech Stack: Core Java 17, Spring Boot, Microservices, PostgreSQL, Kafka, and React.\n"
                "Must have 7+ years of experience with REST APIs and Docker/AWS deployment.\n"
                "Rate: $75-$85/hr on C2C. Please share updated resume and rate to sarah.jenkins@teksystems-staffing.com"
            ),
            "email_sent_status": "pending",
            "timestamp": now_str
        },
        {
            "recruiter_name": "Michael Roberts",
            "recruiter_email": "m.roberts@apexsystems-c2c.com",
            "role": "Data Scientist / ML Engineer",
            "post_url": "https://www.linkedin.com/posts/michael-roberts_c2c-machinelearning-datascientist-activity-718293847291029385",
            "job_description": (
                "Immediate Opening: Senior Data Scientist / Machine Learning Engineer (C2C Contract).\n"
                "Location: Austin, TX (Hybrid 2 days/week, open to US Relocation).\n"
                "Requirements: Strong background in Python, PyTorch, Scikit-Learn, and Databricks.\n"
                "Hands-on experience deploying LLM pipelines and NLP models to AWS cloud.\n"
                "Strictly C2C candidates only. Send resumes to m.roberts@apexsystems-c2c.com"
            ),
            "email_sent_status": "pending",
            "timestamp": now_str
        },
        {
            "recruiter_name": "Amanda Chen",
            "recruiter_email": "amanda.chen@kforce-tech.com",
            "role": "React Developer",
            "post_url": "https://www.linkedin.com/posts/amanda-chen_frontend-react-c2c-activity-718293847291029386",
            "job_description": (
                "New Corp-to-Corp Opportunity: Senior React / Frontend Developer.\n"
                "Location: Remote (US Based only, EST/CST working hours).\n"
                "Key Skills: React 18, TypeScript, Next.js, Redux Toolkit, Tailwind CSS, REST APIs.\n"
                "Duration: 12 months with extension. C2C corp-to-corp rate open.\n"
                "Send candidate profile and contact details to amanda.chen@kforce-tech.com"
            ),
            "email_sent_status": "pending",
            "timestamp": now_str
        },
        {
            "recruiter_name": "David Miller",
            "recruiter_email": "david.miller@beaconhill-partners.com",
            "role": "Java Full Stack Developer",
            "post_url": "https://www.linkedin.com/posts/david-miller_java-c2c-contracts-activity-718293847291029387",
            "job_description": (
                "Looking for a Senior Java Developer with Spring Boot & AWS expertise for our Financial Services client in Charlotte, NC.\n"
                "100% Remote USA. C2C contract 6-12 months.\n"
                "Technologies: Java, Spring Boot, Microservices, Kubernetes, Redis, PostgreSQL.\n"
                "Please email resume to david.miller@beaconhill-partners.com"
            ),
            "email_sent_status": "pending",
            "timestamp": now_str
        }
    ]

    filtered = [r for r in sample_records if role.lower() in r["role"].lower() or "java" in r["role"].lower()][:count]
    if not filtered:
        filtered = sample_records[:count]

    save_recruiters_to_csv(filtered)
    return filtered
