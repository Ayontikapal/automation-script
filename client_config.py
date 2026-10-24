"""
client_config.py - Core configuration for candidate profiles, role mappings,
C2C filtering parameters, 60+ technology keywords, and database schemas.
"""

import os
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).parent.resolve()
CLIENTS_DIR = BASE_DIR / "clients"
SCRATCH_DIR = BASE_DIR / "scratch"
RECRUITERS_CSV = BASE_DIR / "recruiters.csv"
EMAIL_SENT_HISTORY_CSV = BASE_DIR / "email_sent_history.csv"
SESSION_JSON = BASE_DIR / "session.json"

# Ensure directories exist
CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# 1. Candidate Role Configurations & Search Mapping
# ---------------------------------------------------------
CANDIDATE_ROLES: Dict[str, Dict[str, Any]] = {
    "safi": {
        "primary_role": "Java Full Stack Developer",
        "search_roles": [
            "Java Developer",
            "Java Full Stack Developer",
            "Spring Boot Developer",
            "Backend Java Engineer"
        ],
        "exclusion_keywords": ["hotlist", "fulltime", "available consultants", "bench", "w2 only", "no c2c"],
        "target_skills": ["Java", "Spring Boot", "Microservices", "PostgreSQL", "Kafka", "Docker", "AWS", "REST API"],
        "customizer_module": "safi_customizer"
    },
    "tanuja": {
        "primary_role": "Data Scientist / ML Engineer",
        "search_roles": [
            "Data Scientist",
            "Machine Learning Engineer",
            "AI Engineer",
            "Python Data Engineer"
        ],
        "exclusion_keywords": ["hotlist", "fulltime", "available consultants", "bench", "w2 only", "no c2c"],
        "target_skills": ["Python", "PyTorch", "TensorFlow", "Scikit-Learn", "Machine Learning", "NLP", "LLM", "SQL", "Databricks"],
        "customizer_module": "tanuja_customizer"
    },
    "jane_doe": {
        "primary_role": "React Developer",
        "search_roles": [
            "React Developer",
            "Frontend Engineer",
            "UI Developer",
            "Full Stack React Developer"
        ],
        "exclusion_keywords": ["hotlist", "fulltime", "available consultants", "bench", "w2 only", "no c2c"],
        "target_skills": ["React", "TypeScript", "JavaScript", "Redux", "Next.js", "Tailwind CSS", "HTML5", "CSS3", "REST API"],
        "customizer_module": None
    }
}

# ---------------------------------------------------------
# 2. Registered Client Profiles
# ---------------------------------------------------------
CLIENTS: Dict[str, Dict[str, Any]] = {
    "safi": {
        "name": "Safi Ahmed",
        "email": "safi.ahmed.c2c@example.com",
        "phone": "+1 (469) 555-0142",
        "linkedin": "https://www.linkedin.com/in/safi-ahmed-dev",
        "location": "Dallas, TX",
        "relocation": "Yes (Open to Remote / Hybrid / Relocation across US)",
        "work_auth": "C2C / Corp-to-Corp",
        "availability": "Immediate",
        "experience": "8+ Years",
        "resume_candidates": [
            str(CLIENTS_DIR / "safi_resume.docx")
        ],
        "summary": "Accomplished Java Full Stack Developer with 8+ years designing scalable microservices, high-throughput cloud backends, and robust enterprise applications.",
        "team_lead_cc": "lead.recruitment@example.com",
        "admin_bcc": "admin.outreach@example.com"
    },
    "tanuja": {
        "name": "Tanuja Sharma",
        "email": "tanuja.sharma.ml@example.com",
        "phone": "+1 (512) 555-0188",
        "linkedin": "https://www.linkedin.com/in/tanuja-sharma-ai",
        "location": "Austin, TX",
        "relocation": "Yes (Open to Remote / Hybrid across US)",
        "work_auth": "C2C / Corp-to-Corp",
        "availability": "Immediate",
        "experience": "7+ Years",
        "resume_candidates": [
            str(CLIENTS_DIR / "tanuja_resume.docx")
        ],
        "summary": "Senior Data Scientist & Machine Learning Specialist with 7+ years delivering end-to-end predictive modeling, generative AI pipelines, and large-scale big data analytics.",
        "team_lead_cc": "lead.recruitment@example.com",
        "admin_bcc": "admin.outreach@example.com"
    },
    "jane_doe": {
        "name": "Jane Doe",
        "email": "janedoe@example.com",
        "phone": "555-019-2834",
        "linkedin": "https://www.linkedin.com/in/janedoe",
        "location": "Dallas, TX",
        "relocation": "Yes",
        "work_auth": "H1B / C2C",
        "availability": "Immediate",
        "experience": "5+ Years",
        "resume_candidates": [
            str(CLIENTS_DIR / "jane_doe_resume.docx")
        ],
        "summary": "Experienced Frontend / React Developer with 5+ years building dynamic, responsive single-page web applications with modern TypeScript and component libraries.",
        "team_lead_cc": "lead.recruitment@example.com",
        "admin_bcc": "admin.outreach@example.com"
    }
}

# ---------------------------------------------------------
# 3. Dynamic Hooking: 60+ Technology Keywords
# ---------------------------------------------------------
JD_KEYWORDS: List[str] = [
    # Languages & Frameworks
    "Java", "Spring Boot", "Microservices", "Hibernate", "Kotlin", "Scala",
    "Python", "Django", "Flask", "FastAPI", "Pandas", "NumPy", "Scikit-Learn",
    "PyTorch", "TensorFlow", "Keras", "Hugging Face", "LLM", "NLP", "LangChain",
    "JavaScript", "TypeScript", "React", "Angular", "Vue", "Next.js", "Node.js", "Express",
    "C#", ".NET", "ASP.NET", "C++", "Golang", "Rust", "PHP", "Ruby on Rails",
    # Databases & Caching
    "SQL", "PostgreSQL", "MySQL", "Oracle", "SQL Server", "MongoDB", "Cassandra",
    "Redis", "Elasticsearch", "DynamoDB", "Snowflake", "Databricks", "BigQuery",
    # Cloud, DevOps & Containers
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "OpenShift", "Terraform",
    "Jenkins", "GitHub Actions", "GitLab CI", "CI/CD", "Helm", "Ansible",
    # Messaging & Streaming
    "Kafka", "RabbitMQ", "Apache Spark", "Airflow", "dbt", "GraphQL", "REST API",
    # UI / Styling & Analytics
    "Tailwind CSS", "Bootstrap", "Redux", "Tableau", "PowerBI"
]

# ---------------------------------------------------------
# 4. Strict Filtering Criteria
# ---------------------------------------------------------
NON_USA_INDICATORS: List[str] = [
    "pune", "noida", "hyderabad", "bangalore", "bengaluru", "chennai", "mumbai",
    "gurgaon", "gurugram", "delhi", "kolkata", "ahmedabad", "india", "canada",
    "toronto", "vancouver", "montreal", "united kingdom", "london", "philippines",
    "pakistan", "uae", "dubai", "singapore", "australia", "sydney", "latin america",
    "mexico", "brazil", "nigeria", "ukraine", "poland"
]

US_LOCATION_INDICATORS: List[str] = [
    # States and abbreviations
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    # Explicit terms
    "usa", "united states", "remote in us", "us remote", "u.s.", "cst", "est", "pst", "mst",
    # Major US Cities
    "dallas", "austin", "houston", "san antonio", "new york", "chicago", "atlanta",
    "seattle", "san francisco", "san jose", "los angeles", "boston", "denver",
    "phoenix", "charlotte", "philadelphia", "minneapolis", "raleigh", "tampa", "miami"
]

BENCH_INDICATORS: List[str] = [
    "on my bench",
    "candidate available",
    "marketing my consultant",
    "hotlist",
    "available consultants",
    "bench sales",
    "bench consultant",
    "sharing hotlist",
    "my consultant",
    "below is my hotlist",
    "anyone looking for consultants",
    "our bench candidates",
    "send me c2c requirements"
]

DOMAIN_EXCLUSIONS: Dict[str, List[str]] = {
    "Java Full Stack Developer": [
        "devops", "devops lead", "devops engineer", "qa", "qa lead", "qa tester",
        "manual qa", "manual tester", "salesforce", "salesforce developer", "sap",
        "sap abap", "scrum master", "product manager", "servicenow", "mainframe", "network admin"
    ],
    "Data Scientist / ML Engineer": [
        "salesforce", "qa", "qa engineer", "qa tester", "scrum master", "ios developer",
        "android developer", "sap", "servicenow", "mainframe", "helpdesk"
    ],
    "React Developer": [
        "devops", "devops engineer", "qa", "qa automation", "manual qa", "qa tester",
        "salesforce", "sap", "embedded c", "hardware engineer", "network engineer", "dba"
    ]
}

# ---------------------------------------------------------
# 5. Database Schema Definitions
# ---------------------------------------------------------
RECRUITERS_SCHEMA = [
    "recruiter_name",
    "recruiter_email",
    "role",
    "post_url",
    "job_description",
    "email_sent_status",  # pending, sent, failed, mismatched_role
    "timestamp"           # YYYY-MM-DD HH:MM:SS
]

EMAIL_SENT_HISTORY_SCHEMA = [
    "recruiter_name",
    "recruiter_email",
    "role",
    "post_url",
    "candidate",
    "email_sent_status",  # sent, failed
    "timestamp",          # YYYY-MM-DD HH:MM:SS
    "subject",
    "message_id",
    "followup_count",     # int default 0
    "last_followup_at",   # timestamp or empty
    "replied"             # int: 0 or 1
]


def init_database_files():
    """Initializes and migrates CSV database files if missing or missing columns."""
    import pandas as pd

    # 1. Recruiters CSV
    if not RECRUITERS_CSV.exists() or RECRUITERS_CSV.stat().st_size == 0:
        df = pd.DataFrame(columns=RECRUITERS_SCHEMA)
        df.to_csv(RECRUITERS_CSV, index=False)
    else:
        df = pd.read_csv(RECRUITERS_CSV)
        missing_cols = [c for c in RECRUITERS_SCHEMA if c not in df.columns]
        if missing_cols:
            for col in missing_cols:
                df[col] = ""
            df = df[RECRUITERS_SCHEMA]
            df.to_csv(RECRUITERS_CSV, index=False)

    # 2. Email Sent History CSV
    if not EMAIL_SENT_HISTORY_CSV.exists() or EMAIL_SENT_HISTORY_CSV.stat().st_size == 0:
        df = pd.DataFrame(columns=EMAIL_SENT_HISTORY_SCHEMA)
        df.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)
    else:
        df = pd.read_csv(EMAIL_SENT_HISTORY_CSV)
        missing_cols = [c for c in EMAIL_SENT_HISTORY_SCHEMA if c not in df.columns]
        if missing_cols:
            for col in missing_cols:
                if col == "followup_count" or col == "replied":
                    df[col] = 0
                else:
                    df[col] = ""
            df = df[EMAIL_SENT_HISTORY_SCHEMA]
            df.to_csv(EMAIL_SENT_HISTORY_CSV, index=False)
