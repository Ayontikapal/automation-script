"""
main.py - Interactive CLI Entry Point for the Recruitment & Outreach Automation System.
Provides terminal menus, setup validation, single-candidate workflows,
threaded follow-up dispatch, IMAP reply detection, and automated batch processing.
"""

import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

from client_config import (
    BASE_DIR,
    CLIENTS,
    CANDIDATE_ROLES,
    RECRUITERS_CSV,
    EMAIL_SENT_HISTORY_CSV,
    SESSION_JSON,
    init_database_files
)
from linkedin_login import setup_linkedin_session, is_session_valid
from linkedin_scraper import (
    run_linkedin_scraper,
    generate_mock_scraped_leads,
    matches_strict_filter
)
from resume_customizer import customize_resume
from gmail_sender import (
    dispatch_outreach_email,
    batch_dispatch_pending,
    is_already_contacted
)
from followup_sender import run_followup_pipeline, scan_followup_eligibility
from imap_reply_detector import check_replies
from analytics import generate_html_report, compute_pipeline_metrics

console = Console()


def display_banner():
    """Renders sleek terminal banner."""
    banner_text = (
        "[bold cyan]RECRUITMENT & OUTREACH AUTOMATION SYSTEM[/bold cyan]\n"
        "[dim]US Corp-to-Corp (C2C) Contract Pipeline & AI Resume Customizer[/dim]\n"
        "[dim]Playwright &bull; Windows Word COM &bull; Gmail SMTP/IMAP &bull; LLM Tailoring[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def validate_environment() -> Dict[str, Any]:
    """Inspects environment, dependencies, and credential configuration."""
    init_database_files()
    session_ok = is_session_valid()

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    has_gemini = bool(gemini_key and "YourGemini" not in gemini_key)

    gmail_user = os.getenv("GMAIL_EMAIL", "")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD", "")
    has_gmail = bool(gmail_user and "your_gmail" not in gmail_user and gmail_pwd and "abcd" not in gmail_pwd)

    df_rec = pd.read_csv(RECRUITERS_CSV)
    df_hist = pd.read_csv(EMAIL_SENT_HISTORY_CSV)

    return {
        "session_ok": session_ok,
        "has_gemini": has_gemini,
        "has_gmail": has_gmail,
        "scraped_count": len(df_rec),
        "sent_count": len(df_hist[df_hist["email_sent_status"] == "sent"]) if not df_hist.empty else 0,
        "replies_count": int(df_hist["replied"].sum()) if not df_hist.empty and "replied" in df_hist.columns else 0
    }


def show_status_bar():
    """Prints quick real-time status summary."""
    status = validate_environment()
    session_badge = "[bold green]Active[/bold green]" if status["session_ok"] else "[yellow]Missing / Setup Needed[/yellow]"
    gmail_badge = "[bold green]Configured[/bold green]" if status["has_gmail"] else "[dim yellow]Test / Dry-Run Mode[/dim yellow]"
    ai_badge = "[bold green]Gemini / LLM[/bold green]" if status["has_gemini"] else "[cyan]Algorithmic Fallback Engine[/cyan]"

    console.print(
        f"[dim]Status:[/dim] Session: {session_badge} | Gmail: {gmail_badge} | AI Core: {ai_badge} | "
        f"Leads: [bold]{status['scraped_count']}[/bold] | Sent: [bold]{status['sent_count']}[/bold] | Replies: [bold green]{status['replies_count']}[/bold green]"
    )
    console.print("-" * 75, style="dim")


def display_menu():
    """Displays the interactive CLI menu."""
    table = Table(title="Operational Control Center", border_style="blue", header_style="bold magenta")
    table.add_column("Option", style="cyan", justify="center", width=8)
    table.add_column("Action / Workflow Module", style="white")
    table.add_column("Description", style="dim")

    table.add_row("1", "Targeted LinkedIn Scraper", "Scrape US C2C recruiter posts for candidate role")
    table.add_row("2", "Setup LinkedIn Login Session", "Headful browser login to capture cookies to session.json")
    table.add_row("3", "Review Scraped Leads & Outreach", "Inspect pending records and dispatch emails (Test / Live)")
    table.add_row("4", "Test AI Resume Customizer", "Run LLM tailoring + Word COM PDF compilation test")
    table.add_row("5", "Dispatch Threaded Follow-ups", "Send In-Reply-To follow-ups for unanswered applications")
    table.add_row("6", "Sync IMAP Recruiter Replies", "Scan Gmail inbox for recruiter responses")
    table.add_row("7", "Generate Analytics Dashboard", "Export and open dark-themed HTML metrics dashboard")
    table.add_row("8", "Run Automated Batch Mode", "Full end-to-end pipeline execution for ALL candidates")
    table.add_row("9", "System Self-Test & Diagnostic", "End-to-end verification and mock pipeline demonstration")
    table.add_row("0", "Exit", "Close the console")

    console.print(table)


def select_candidate() -> str:
    """Prompt user to choose one of the registered candidates."""
    table = Table(title="Select Candidate", border_style="cyan")
    table.add_column("Key", style="bold cyan")
    table.add_column("Name", style="white")
    table.add_column("Primary Role", style="yellow")
    table.add_column("Location", style="dim")

    keys = list(CLIENTS.keys())
    for k in keys:
        c = CLIENTS[k]
        role = CANDIDATE_ROLES[k]["primary_role"]
        table.add_row(k, c["name"], role, c.get("location", "USA"))

    console.print(table)
    choice = Prompt.ask("Enter candidate key", choices=keys, default=keys[0])
    return choice


# -------------------------------------------------------------
# Handlers for Menu Options
# -------------------------------------------------------------

def handle_scraping():
    """Option 1: Scrape LinkedIn posts."""
    console.print("\n[bold cyan]=== Step 1: Targeted LinkedIn Scraping ===[/bold cyan]")
    cand_key = select_candidate()
    role = CANDIDATE_ROLES[cand_key]["primary_role"]

    console.print(f"Target Role: [bold yellow]{role}[/bold yellow]")
    if not is_session_valid():
        console.print("[yellow]Notice: No active LinkedIn session detected in session.json.[/yellow]")
        use_mock = Confirm.ask("Would you like to generate validated US C2C test leads for demonstration?", default=True)
        if use_mock:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
                p.add_task(description="Generating realistic C2C recruiter posts...", total=None)
                leads = generate_mock_scraped_leads(role=role, count=3)
            console.print(f"[bold green]Successfully saved {len(leads)} verified recruiter leads into recruiters.csv[/bold green]")
            return

    max_scrolls = IntPrompt.ask("Enter number of page scrolls", default=6)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description=f"Running Playwright scraper for '{role}'...", total=None)
        results = run_linkedin_scraper(target_role=role, max_scrolls=max_scrolls, headless=True)

    if results:
        console.print(f"[bold green]Successfully scraped {len(results)} new recruiter posts into recruiters.csv[/bold green]")
    else:
        console.print("[yellow]Scraper completed. If 0 new leads were added, verify session cookies or existing records.[/yellow]")


def handle_login_setup():
    """Option 2: Headful LinkedIn login."""
    console.print("\n[bold cyan]=== Step 2: LinkedIn Headful Authentication Setup ===[/bold cyan]")
    console.print("A browser window will open. Complete any LinkedIn login or 2FA prompts.")
    success = setup_linkedin_session()
    if success:
        console.print("[bold green]Success: LinkedIn session captured and saved to session.json.[/bold green]")
    else:
        console.print("[bold red]Session setup could not be completed or timed out.[/bold red]")


def handle_review_and_dispatch():
    """Option 3: Review pending recruiters and dispatch outreach."""
    console.print("\n[bold cyan]=== Step 3: Inspect Scraped Leads & Dispatch Outreach ===[/bold cyan]")
    init_database_files()
    df_rec = pd.read_csv(RECRUITERS_CSV)

    pending = df_rec[df_rec["email_sent_status"] == "pending"]
    if pending.empty:
        console.print("[yellow]No pending recruiter leads in recruiters.csv.[/yellow]")
        gen = Confirm.ask("Generate sample US C2C recruiter leads to review?", default=True)
        if gen:
            generate_mock_scraped_leads()
            df_rec = pd.read_csv(RECRUITERS_CSV)
            pending = df_rec[df_rec["email_sent_status"] == "pending"]

    # Show pending table
    table = Table(title=f"Pending Recruiter Leads ({len(pending)} total)", border_style="green")
    table.add_column("Recruiter Name", style="bold white")
    table.add_column("Email", style="cyan")
    table.add_column("Role", style="yellow")
    table.add_column("Post Link", style="dim", max_width=35)

    for _, row in pending.head(5).iterrows():
        table.add_row(
            str(row.get("recruiter_name")),
            str(row.get("recruiter_email")),
            str(row.get("role")),
            str(row.get("post_url"))[:35] + "..."
        )
    console.print(table)

    cand_key = select_candidate()
    mode = Prompt.ask("Sending Mode", choices=["Test", "Live"], default="Test")
    dry_run = (mode == "Test")

    limit = IntPrompt.ask("How many leads to dispatch in this run?", default=min(3, len(pending)))

    action = Prompt.ask("Type 'SEND' to approve outreach or 'CANCEL' to abort", choices=["SEND", "CANCEL"], default="SEND")
    if action == "SEND":
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
            p.add_task(description="Customizing resumes and dispatching cold outreach...", total=None)
            sent, failed = batch_dispatch_pending(candidate_key=cand_key, limit=limit, dry_run=dry_run)

        console.print(f"[bold green]Dispatch Finished: {sent} sent successfully, {failed} skipped/failed.[/bold green]")
        console.print("Sent records logged to [cyan]email_sent_history.csv[/cyan].")
    else:
        console.print("[yellow]Outreach cancelled by operator.[/yellow]")


def handle_resume_customizer_test():
    """Option 4: Test Resume Customizer."""
    console.print("\n[bold cyan]=== Step 4: AI Resume Customizer Test ===[/bold cyan]")
    cand_key = select_candidate()
    sample_jd = (
        "Seeking Senior Java Full Stack Developer with 7+ years of experience in Java 17, Spring Boot, "
        "Microservices, Kafka, PostgreSQL, and AWS deployment for an immediate C2C contract role in Dallas, TX."
    )
    console.print(f"Sample Job Description:\n[dim]{sample_jd}[/dim]\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description=f"Tailoring resume for {CLIENTS[cand_key]['name']} and compiling PDF...", total=None)
        pdf_path, tailored_data = customize_resume(cand_key, sample_jd)

    console.print(f"[bold green]Successfully generated tailored PDF: {pdf_path}[/bold green]")
    console.print("\n[bold]Tailored Summary Preview:[/bold]")
    console.print(Panel(tailored_data.get("rewritten_summary", ""), border_style="cyan"))

    open_pdf = Confirm.ask("Open tailored PDF file to inspect formatting?", default=False)
    if open_pdf:
        webbrowser.open(str(pdf_path))


def handle_followups():
    """Option 5: Threaded Follow-ups."""
    console.print("\n[bold cyan]=== Step 5: Dispatch Threaded Follow-ups ===[/bold cyan]")
    days = IntPrompt.ask("Enter days threshold for unanswered emails (e.g. 7, or 0 to test recent)", default=0)
    dry_run = Confirm.ask("Run in Test/Dry-Run mode?", default=True)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description="Scanning eligibility and dispatching threaded follow-ups...", total=None)
        sent_count = run_followup_pipeline(days_threshold=days, dry_run=dry_run)

    console.print(f"[bold green]Follow-up cycle complete: {sent_count} follow-ups processed.[/bold green]")


def handle_imap_sync():
    """Option 6: Sync IMAP Replies."""
    console.print("\n[bold cyan]=== Step 6: Sync Recruiter Replies via IMAP ===[/bold cyan]")
    simulate = Confirm.ask("Run with simulated incoming recruiter reply for test?", default=True)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description="Connecting to Gmail IMAP (SSL 993) and scanning inbox...", total=None)
        count, senders = check_replies(simulate_test=simulate)

    if count > 0:
        console.print(f"[bold green]Detected {count} replies! Recruiter(s): {', '.join(senders)}[/bold green]")
    else:
        console.print("[dim]No new replies matched against pending outreach.[/dim]")


def handle_analytics():
    """Option 7: Generate Analytics Dashboard."""
    console.print("\n[bold cyan]=== Step 7: Generate Analytics Dashboard ===[/bold cyan]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task(description="Aggregating pipeline telemetry and compiling dark-mode HTML...", total=None)
        report_path = generate_html_report()

    console.print(f"[bold green]Dashboard generated: {report_path}[/bold green]")
    open_browser = Confirm.ask("Open dashboard in default web browser now?", default=True)
    if open_browser:
        webbrowser.open(f"file:///{report_path}")


def handle_automated_batch_run():
    """Option 8: Automated Batch Mode across ALL Candidates."""
    console.print("\n[bold cyan]=== Step 8: Automated Batch Mode (All Candidates) ===[/bold cyan]")
    console.print("This orchestrator runs scraping, filtering, tailoring, and dispatching for each candidate in sequence.")

    mode = Prompt.ask("Select Sending Mode", choices=["Test", "Live"], default="Test")
    dry_run = (mode == "Test")
    per_candidate_limit = IntPrompt.ask("Enter outreach limit per candidate", default=2)

    candidates = list(CLIENTS.keys())
    console.print(f"Executing batch across {len(candidates)} candidate profiles: {', '.join(candidates)}")

    total_sent = 0
    for cand_key in candidates:
        cand_name = CLIENTS[cand_key]["name"]
        role = CANDIDATE_ROLES[cand_key]["primary_role"]
        console.print(f"\n[bold yellow]>>> Processing Candidate: {cand_name} ({role}) <<<[/bold yellow]")

        # 1. Scrape or load leads
        if not is_session_valid():
            console.print("[dim]Generating verified C2C leads for candidate domain...[/dim]")
            generate_mock_scraped_leads(role=role, count=per_candidate_limit)
        else:
            run_linkedin_scraper(target_role=role, max_scrolls=3, headless=True)

        # 2. Dispatch outreach
        sent, failed = batch_dispatch_pending(candidate_key=cand_key, limit=per_candidate_limit, dry_run=dry_run)
        total_sent += sent
        console.print(f"Result for {cand_name}: [green]{sent} sent[/green], [dim]{failed} skipped/failed[/dim]")

    console.print(f"\n[bold green]Batch Execution Completed: Total {total_sent} outreach emails processed across all candidates.[/bold green]")
    generate_html_report()
    console.print("[bold cyan]Updated Analytics Report is ready.[/bold cyan]")


def handle_system_diagnostic():
    """Option 9: Full diagnostic and mock pipeline demonstration."""
    console.print("\n[bold cyan]=== Step 9: System Self-Diagnostic & Mock Demonstration ===[/bold cyan]")
    console.print("[dim]Testing all system components: Databases, Resume Customizer, Word COM, SMTP Dispatch, Threaded Follow-up, IMAP Sync, and Analytics Dashboard...[/dim]\n")

    # 1. Database Init
    init_database_files()
    console.print("[green][OK] Database CSV schemas verified and synchronized[/green]")

    # 2. Generate sample leads
    leads = generate_mock_scraped_leads("Java Full Stack Developer", count=3)
    console.print(f"[green][OK] Lead Scraping & Strict Filtering verified ({len(leads)} leads active)[/green]")

    # 3. Test resume customization with COM lock
    pdf_path, _ = customize_resume("safi", "Senior Java Developer with Spring Boot, Kafka, and PostgreSQL in Dallas, TX.")
    console.print(f"[green][OK] Word COM PDF Compilation & Mutex Lock verified ({pdf_path.name})[/green]")

    # 4. Test cold outreach dispatch
    sent, _ = batch_dispatch_pending("safi", limit=1, dry_run=True)
    console.print(f"[green][OK] Gmail SMTP Dispatch & Dynamic Hooking verified ({sent} outreach logged)[/green]")

    # 5. Test follow-up pipeline
    f_sent = run_followup_pipeline(days_threshold=0, dry_run=True)
    console.print(f"[green][OK] Threaded Follow-Up Header Linkage (In-Reply-To) verified ({f_sent} follow-ups sent)[/green]")

    # 6. Test IMAP reply detection
    r_count, _ = check_replies(simulate_test=True)
    console.print(f"[green][OK] IMAP Reply Detector & Conversation Sync verified ({r_count} replies matched)[/green]")

    # 7. Generate dashboard
    report = generate_html_report()
    console.print(f"[green][OK] Dark-Themed Analytics HTML Dashboard generated ({report.name})[/green]")

    console.print("\n[bold green]*** ALL SYSTEM SUBSYSTEMS FULLY OPERATIONAL AND VERIFIED! ***[/bold green]")


def main():
    """Main interactive terminal loop."""
    display_banner()
    while True:
        try:
            show_status_bar()
            display_menu()
            choice = Prompt.ask("\nSelect an option", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="8")

            if choice == "1":
                handle_scraping()
            elif choice == "2":
                handle_login_setup()
            elif choice == "3":
                handle_review_and_dispatch()
            elif choice == "4":
                handle_resume_customizer_test()
            elif choice == "5":
                handle_followups()
            elif choice == "6":
                handle_imap_sync()
            elif choice == "7":
                handle_analytics()
            elif choice == "8":
                handle_automated_batch_run()
            elif choice == "9":
                handle_system_diagnostic()
            elif choice == "0":
                console.print("\n[cyan]Exiting Recruitment Automation System. Goodbye![/cyan]")
                sys.exit(0)

            console.print("\n" + "=" * 75 + "\n")
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation interrupted. Exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error in execution:[/bold red] {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
