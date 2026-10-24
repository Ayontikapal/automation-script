"""
safi_customizer.py - Dedicated resume customizer hook for Safi Ahmed (Java Full Stack Developer).
Implements custom structural parsing, style-preserving XML run rewriting, and tailoring for Safi's resume layout.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("safi_customizer")


def customize_safi_resume(doc, tailored_data: Dict[str, Any]) -> None:
    """
    Applies custom run-by-run style-preserving updates to Safi's resume.
    Preserves exact font names, sizes, bold, italic, colors, and paragraph styles.
    """
    summary_text = tailored_data.get("rewritten_summary", "")
    new_bullets = tailored_data.get("rewritten_paragraphs", [])
    skills_text = tailored_data.get("rewritten_skills", "")

    in_summary = False
    in_experience = False
    bullet_idx = 0

    for paragraph in doc.paragraphs:
        p_text = paragraph.text.strip().upper()

        # Section boundaries
        if "PROFESSIONAL SUMMARY" in p_text or "SUMMARY" in p_text:
            in_summary = True
            in_experience = False
            continue
        elif "TECHNICAL SKILLS" in p_text or "CORE COMPETENCIES" in p_text:
            in_summary = False
            in_experience = False
            continue
        elif "WORK EXPERIENCE" in p_text or "PROFESSIONAL EXPERIENCE" in p_text or "PROJECTS" in p_text:
            in_summary = False
            in_experience = True
            continue
        elif any(sec in p_text for sec in ["EDUCATION", "CERTIFICATIONS", "HONORS", "AWARDS"]):
            in_summary = False
            in_experience = False
            continue

        # Summary paragraph injection
        if in_summary and summary_text and paragraph.text.strip():
            _update_paragraph_preserving_runs(paragraph, summary_text)
            summary_text = ""  # injected once
            continue

        # Experience bullets injection
        if in_experience and new_bullets and bullet_idx < len(new_bullets):
            # If paragraph looks like a bullet or achievement
            if paragraph.text.strip() and not _is_job_title_or_date(paragraph.text):
                _update_paragraph_preserving_runs(paragraph, new_bullets[bullet_idx])
                bullet_idx += 1
                continue

    # Table parsing for Technical Skills if embedded in a table
    if skills_text:
        _update_skills_in_tables_or_text(doc, skills_text)


def _is_job_title_or_date(text: str) -> bool:
    """Checks if line is a job header or company/date line."""
    text_lower = text.lower()
    if any(m in text_lower for m in ["2020", "2021", "2022", "2023", "2024", "2025", "present"]):
        return True
    if any(title in text_lower for title in ["developer", "engineer", "lead", "architect", "consultant"]):
        if len(text.split()) < 8:
            return True
    return False


def _update_paragraph_preserving_runs(paragraph, new_text: str):
    """
    Style-Preserving XML Re-write:
    Walks runs, overwriting text while preserving font properties of the original run.
    """
    if not paragraph.runs:
        paragraph.text = new_text
        return

    first_run = paragraph.runs[0]
    first_run.text = new_text

    # Clear subsequent runs to avoid trailing residual text while preserving paragraph styling
    for r in paragraph.runs[1:]:
        r.text = ""


def _update_skills_in_tables_or_text(doc, skills_text: str):
    """Finds skills cells or paragraphs and updates them."""
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if any(k in cell.text.lower() for k in ["languages", "frameworks", "tools", "databases"]):
                    for p in cell.paragraphs:
                        if p.text.strip():
                            _update_paragraph_preserving_runs(p, skills_text)
                            return
