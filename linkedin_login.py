"""
linkedin_login.py - Automates headful browser login to establish LinkedIn session cookies.
Saves session state to session.json for subsequent headless scraping operations.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from client_config import SESSION_JSON, BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("linkedin_login")


def is_session_valid(session_path: Path = SESSION_JSON) -> bool:
    """
    Checks if session.json exists, has non-empty cookies, and includes li_at or JSESSIONID.
    """
    if not session_path.exists():
        return False
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        if not cookies:
            return False
        # Look for core LinkedIn auth cookie
        cookie_names = {c.get("name") for c in cookies}
        return "li_at" in cookie_names or "JSESSIONID" in cookie_names
    except Exception as e:
        logger.debug(f"Error inspecting session.json: {e}")
        return False


def setup_linkedin_session(
    email: str = None,
    password: str = None,
    timeout_seconds: int = 180,
    session_path: Path = SESSION_JSON
) -> bool:
    """
    Launches a headful browser for the user to log in to LinkedIn.
    Detects successful landing on home feed or global navigation element,
    saves storage state to session.json, and closes the browser cleanly.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright is not installed. Please install playwright and run 'playwright install'.")
        return False

    email = email or os.getenv("LINKEDIN_EMAIL", "")
    password = password or os.getenv("LINKEDIN_PASSWORD", "")

    logger.info("Launching headful browser for LinkedIn authentication...")
    logger.info(f"Session will be stored in: {session_path}")

    with sync_playwright() as p:
        # Launch headful browser
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )

        context_kwargs = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        # If existing session exists, load it
        if session_path.exists() and session_path.stat().st_size > 10:
            try:
                context = browser.new_context(storage_state=str(session_path), **context_kwargs)
            except Exception:
                context = browser.new_context(**context_kwargs)
        else:
            context = browser.new_context(**context_kwargs)

        page = context.new_page()

        try:
            logger.info("Navigating to LinkedIn Login...")
            page.goto("https://www.linkedin.com/login", timeout=45000)

            # Auto-fill if credentials provided and username field is present
            if email and "example.com" not in email:
                try:
                    if page.is_visible("input#username", timeout=3000):
                        page.fill("input#username", email)
                        if password and "password" not in password:
                            page.fill("input#password", password)
                            logger.info("Auto-filled LinkedIn credentials. Awaiting user submission / 2FA / CAPTCHA...")
                except Exception as e:
                    logger.debug(f"Could not auto-fill login credentials: {e}")

            logger.info("Waiting for successful login (navigating to feed or global navigation detection)...")
            logger.info(f"You have up to {timeout_seconds} seconds to complete any 2FA or CAPTCHA challenges in the browser.")

            start_time = time.time()
            logged_in = False

            while time.time() - start_time < timeout_seconds:
                current_url = page.url
                # Check URL indicators
                if any(x in current_url for x in ["/feed", "/mynetwork", "/jobs", "/messaging"]):
                    logged_in = True
                    break

                # Check DOM indicators
                try:
                    if page.locator("#global-nav, nav.global-nav, .global-nav__content, button[data-control-name='nav.settings_signout']").count() > 0:
                        logged_in = True
                        break
                except Exception:
                    pass

                time.sleep(1.0)

            if logged_in:
                # Give a brief moment for all auth cookies to settle
                page.wait_for_timeout(3000)
                session_path.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(session_path))
                logger.info(f"SUCCESS: LinkedIn session cookies captured and saved to '{session_path}'.")
                return True
            else:
                logger.warning("Timed out waiting for LinkedIn login completion.")
                return False

        except Exception as e:
            logger.error(f"Error during LinkedIn login setup: {e}")
            return False
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    success = setup_linkedin_session()
    sys.exit(0 if success else 1)
