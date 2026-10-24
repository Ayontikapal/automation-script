# Recruitment & Outreach Automation System

A command-line driven pipeline designed to automate cold outreach to recruiters on LinkedIn for contract positions (specifically focusing on **Corp-to-Corp (C2C)** roles in the United States). It operates in **Client Application Mode** to manage and automate C2C contract outreach on behalf of registered client candidates.

---

## Architecture Blueprint & Core Components

```
automation-project/
├── main.py                     # Interactive CLI console (9 operational modules)
├── client_config.py            # Registered candidates, 60+ JD keywords, C2C exclusion filters, CSV schemas
├── lock_util.py                # Process-safe & thread-safe MS Word COM mutex lock with watchdog
├── linkedin_login.py           # Headful Playwright script to capture cookies to session.json
├── linkedin_scraper.py         # Playwright scraper with Three-Dots Clipboard Interceptor & strict filters
├── resume_customizer.py        # Core AI document customizer with XML run-by-run style preservation & COM PDF compilation
├── safi_customizer.py          # Dedicated resume customizer hook for Safi Ahmed (Java Full Stack)
├── tanuja_customizer.py        # Dedicated resume customizer hook for Tanuja Sharma (Data Scientist / ML)
├── gmail_sender.py             # Dual SMTP negotiation (587 STARTTLS / 465 SSL), 3s anti-throttling, dynamic hooks
├── followup_sender.py          # Threaded follow-ups with In-Reply-To & References header linkage & AI value prop
├── imap_reply_detector.py      # IMAP SSL (port 993) inbox sync with date windowing and batch header parsing
├── analytics.py                # Statistics computation and export of premium dark-themed analytics_report.html
├── generate_client_resumes.py  # Utility script to generate candidate baseline resume templates
├── requirements.txt            # System dependencies matching Blueprint section 6.1
├── .env.example                # Template for credentials and API keys
├── session.json                # Playwright browser state (cookies, local storage)
├── recruiters.csv              # Database of scraped recruiter contacts
├── email_sent_history.csv      # Database of outreach history, follow-ups, and reply statuses
├── analytics_report.html       # Standalone dark-themed conversion dashboard with Chart.js
├── clients/                    # Directory containing source DOCX resume templates
└── scratch/                    # Sandbox for intermediate conversions, customized PDFs, and locks
```

---

## 1. Core Capabilities

1. **Targeted Scraping**: Connects to LinkedIn using Playwright, searches for hiring posts matching specific roles (`<Role> + C2C -hotlist -fulltime -\"available consultants\" -Bench`), filters for USA geo-location (`geoUrn=103644278`), and isolates recruiters' contact emails.
2. **Three-Dots Clipboard Interceptor**: Bypasses LinkedIn post link obfuscation by centering the post card, clicking `button[aria-label*='control menu for post']`, triggering "Copy link", and reading `navigator.clipboard.readText()`.
3. **Strict Filtering**: Automatically excludes non-USA locations (`NON_USA_INDICATORS`), bench sales / marketing posts (`BENCH_INDICATORS`), and domain mismatches (`DOMAIN_EXCLUSIONS`).
4. **AI Resume Customization**: Multi-LLM provider chaining (Gemini `gemini-2.0-flash` primary, OpenRouter / Groq fallback, and high-fidelity algorithmic weaver) to rewrite professional summary, project bullets, and technical skills while preserving exact Word XML formatting and styles run-by-run.
5. **Thread-Safe Word COM PDF Compilation**: Uses Windows Microsoft Word COM automation wrapped in a file-based mutex lock (`lock_util.py`) with hung-process recovery (`taskkill /f /im winword.exe`).
6. **Dual SMTP Negotiation & Cold Outreach**: Connects to `smtp.gmail.com:587` with STARTTLS, falling back to `:465` with SSL. Enforces a 3-second anti-throttling sleep delay, extracts top 3 matched technologies from 60+ `JD_KEYWORDS` for contextual dynamic hooks, and attaches randomized timestamped PDFs.
7. **Threaded Follow-Ups**: Scans `email_sent_history.csv` for unanswered outreach older than X days, configures RFC `In-Reply-To` and `References` headers with original `Message-ID`, prepends `"Re: "`, and generates AI value propositions.
8. **IMAP Reply Detection**: Connects to `imap.gmail.com:993` via SSL in read-only mode, searches incoming mail with date-windowing (`SINCE DD-Mon-YYYY`), parses headers in batches of 100, and updates matched recruiters with `replied=1`.
9. **Dark-Themed Analytics HTML Dashboard**: Exports `analytics_report.html` featuring responsive KPI metric cards, Chart.js visual charts, candidate performance tables, and outreach activity logs.

---

## 2. Installation & Quick Start

### 2.1 Prerequisites
- **Operating System**: Windows (required for Microsoft Word COM automation)
- **Python**: 3.10+
- **Microsoft Word**: Installed and licensed on the host system

### 2.2 Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2.3 Configure Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```env
# LinkedIn Credentials
LINKEDIN_EMAIL=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password

# Gmail Credentials (SMTP/IMAP)
GMAIL_EMAIL=your_gmail_address@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop

# AI API Keys
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere
GEMINI_MODEL=gemini-2.0-flash

OPENROUTER_API_KEY=sk-or-v1-yourOpenRouterApiKeyHere
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

GROQ_API_KEY=gsk_yourGroqApiKeyHere
GROQ_MODEL=llama-3.3-70b-versatile
```

---

## 3. Steps to Reproduce (End-to-End Execution Guide)

Follow these exact steps to reproduce, verify, and run the entire automation pipeline from a clean environment:

### Step 1: Environment Setup & Dependency Installation
1. Open PowerShell or Command Prompt in the project root:
   ```powershell
   cd "d:\Ayontika pal\automation-project"
   ```
2. Install the required Python packages and Playwright Chromium binaries:
   ```powershell
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Initialize the environment configuration file:
   ```powershell
   copy .env.example .env
   ```
   *(Note: The system defaults to safe Test/Dry-Run mode when placeholder credentials are used in `.env`)*.

### Step 2: Generate Baseline Candidate Resume Templates
Ensure candidate DOCX resume templates exist in the `clients/` folder:
```powershell
python generate_client_resumes.py
```
This generates baseline templates for **Safi Ahmed** (Java Full Stack Developer), **Tanuja Sharma** (Data Scientist / ML Engineer), and **Jane Doe** (React Developer).

### Step 3: Run the Automated Unit & Integration Test Suite
Execute the test suite to validate all 9 subsystem modules:
```powershell
python test_suite.py
```
**Expected Output:**
```text
test_01_client_config_and_schemas ... ok
test_02_lock_util_mutex ... ok
test_03_scraper_filters_and_cleaning ... ok
test_04_resume_customizer_and_style_preservation ... ok
test_05_client_specific_customizer_hooks ... ok
test_06_gmail_sender_mime_and_hook ... ok
test_07_followup_sender_and_threading_headers ... ok
test_08_imap_reply_detector ... ok
test_09_analytics_computation_and_dashboard ... ok
----------------------------------------------------------------------
Ran 9 tests in ~28s - OK
```

### Step 4: Run the Complete System Self-Diagnostic
Execute the built-in diagnostic routine to test Word COM locking, resume tailoring, simulated outreach dispatch, threaded follow-ups, and IMAP reply detection simultaneously:
```powershell
python -c "from main import handle_system_diagnostic; handle_system_diagnostic()"
```

### Step 5: Run Automated Multi-Candidate Batch Pipeline
Execute continuous batch processing across all candidates defined in `client_config.py`:
```powershell
python -c "from main import handle_automated_batch_run; handle_automated_batch_run()"
```
This automatically scrapes/loads US C2C leads, tailors each resume, and dispatches outreach with anti-throttling.

### Step 6: Launch the Interactive CLI Console
Run the interactive terminal interface:
```powershell
python main.py
```
- Press **`8`** for Automated Batch Mode (All Candidates)
- Press **`3`** to inspect pending recruiter leads and approve outreach (`SEND`)
- Press **`4`** to test AI Resume Customizer and preview tailored PDF
- Press **`5`** to dispatch threaded follow-ups with `In-Reply-To` headers
- Press **`6`** to sync recruiter replies via IMAP
- Press **`7`** to generate the analytics dashboard
- Press **`9`** for System Self-Diagnostic
- Press **`0`** to Exit

### Step 7: View the Analytics Dashboard
Open the compiled dark-themed HTML conversion dashboard in your browser:
```powershell
start analytics_report.html
```

---

## 4. CLI Menu Reference

Launch the interactive console:
```bash
python main.py
```

### Menu Options:
- **`1` Targeted LinkedIn Scraper**: Scrapes US C2C recruiter posts for candidate roles or loads verified demonstration leads.
- **`2` Setup LinkedIn Login Session**: Opens headful browser for manual login / 2FA; saves authenticated session cookies to `session.json`.
- **`3` Review Scraped Leads & Outreach**: Inspects pending records and dispatches personalized outreach emails with customized resume attachments.
- **`4` Test AI Resume Customizer**: Runs prompt tailoring and Word COM PDF compilation test for a selected candidate profile.
- **`5` Dispatch Threaded Follow-ups**: Scans unanswered applications and dispatches threaded follow-ups with `In-Reply-To` headers.
- **`6` Sync IMAP Recruiter Replies**: Scans Gmail inbox via IMAP SSL (993) to detect recruiter responses and marks `replied=1`.
- **`7` Generate Analytics Dashboard**: Re-computes pipeline metrics and opens `analytics_report.html` in your web browser.
- **`8` Run Automated Batch Mode**: Runs continuous scraping, tailoring, and dispatching for ALL registered candidates.
- **`9` System Self-Test & Diagnostic**: Runs an automated end-to-end self-test verifying all components simultaneously.
- **`0` Exit**: Closes the application.

---

## 5. Extending Candidates

To add a new candidate, update `client_config.py`:
1. Add search configuration under `CANDIDATE_ROLES`:
```python
"new_candidate": {
    "primary_role": "React Developer",
    "search_roles": ["React Developer", "Frontend Engineer", "UI Developer"],
    "exclusion_keywords": ["hotlist", "fulltime", "available consultants", "bench"]
}
```
2. Add profile details under `CLIENTS`:
```python
"new_candidate": {
    "name": "Jane Doe",
    "email": "janedoe@example.com",
    "phone": "555-019-2834",
    "linkedin": "https://www.linkedin.com/in/janedoe",
    "location": "Dallas, TX",
    "relocation": "Yes",
    "work_auth": "H1B",
    "availability": "Immediate",
    "experience": "5+ Years",
    "resume_candidates": ["clients/jane_doe_resume.docx"]
}
```
3. Place their DOCX template into `clients/jane_doe_resume.docx`.
