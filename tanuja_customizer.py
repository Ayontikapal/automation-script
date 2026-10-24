"""
tanuja_customizer.py - Dedicated resume customizer hook for Tanuja Sharma (Data Scientist / ML Engineer).
Implements specialized structural parsing and style-preserving run rewriting for Data Science resumes.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("tanuja_customizer")


def customize_tanuja_resume(doc, tailored_data: Dict[str, Any]) -> None:
    """
    Applies custom run-by-run style-preserving updates for Tanuja's Data Science resume.
    Preserves exact font names, sizes, bold, italic, colors, and layout styles.
    """
    summary_text = tailored_data.get("rewritten_summary", "")
    new_bullets = tailored_data.get("rewritten_paragraphs", [])
    skills_text = tailored_data.get("rewritten_skills", "")

    in_summary = False
    in_experience = False
    bullet_idx = 0

    for paragraph in doc.paragraphs:
        p_text = paragraph.text.strip().upper()

        if any(h in p_text for h in ["PROFESSIONAL SUMMARY", "EXECUTIVE SUMMARY", "ABOUT ME"]):
            in_summary = True
            in_experience = False
            continue
        elif any(h in p_text for h in ["TECHNICAL SKILLS", "AREAS OF EXPERTISE", "CORE SKILLS"]):
            in_summary = False
            in_experience = False
            continue
        elif any(h in p_text for h in ["EXPERIENCE", "PROJECT EXPERIENCE", "PROFESSIONAL HISTORY"]):
            in_summary = False
            in_experience = True
            continue
        elif any(h in p_text for h in ["EDUCATION", "PUBLICATIONS", "CERTIFICATIONS"]):
            in_summary = False
            in_experience = False
            continue

        # Summary Injection
        if in_summary and summary_text and paragraph.text.strip():
            _update_paragraph_preserving_runs(paragraph, summary_text)
            summary_text = ""
            continue

        # ML / Project Experience Bullets Injection
        if in_experience and new_bullets and bullet_idx < len(new_bullets):
            if paragraph.text.strip() and not _is_header_or_date(paragraph.text):
                _update_paragraph_preserving_runs(paragraph, new_bullets[bullet_idx])
                bullet_idx += 1
                continue

    # Update skills in tables if present
    if skills_text:
        _update_skills_in_tables(doc, skills_text)


def _is_header_or_date(text: str) -> bool:
    lower = text.lower()
    if any(y in lower for y in ["2021", "2022", "2023", "2024", "2025", "present"]):
        return True
    if any(role in lower for role in ["scientist", "engineer", "lead", "architect", "analyst"]):
        if len(text.split()) < 7:
            return True
    return False


def _update_paragraph_preserving_runs(paragraph, new_text: str):
    if not paragraph.runs:
        paragraph.text = new_text
        return

    first_run = paragraph.runs[0]
    first_run.text = new_text
    for r in paragraph.runs[1:]:
        r.text = ""


def _update_skills_in_tables(doc, skills_text: str):
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if any(k in cell.text.lower() for k in ["machine learning", "libraries", "cloud", "algorithms"]):
                    for p in cell.paragraphs:
                        if p.text.strip():
                            _update_paragraph_preserving_runs(p, skills_text)
                            return
