"""
analytics.py - Generates pipeline statistics and exports a premium dark-themed HTML dashboard.
Analyzes recruiters.csv and email_sent_history.csv to compute conversion KPIs,
candidate performance breakdowns, response rates, and interactive visualizations.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
from client_config import (
    BASE_DIR,
    RECRUITERS_CSV,
    EMAIL_SENT_HISTORY_CSV,
    CLIENTS,
    CANDIDATE_ROLES,
    EMAIL_SENT_HISTORY_SCHEMA,
    init_database_files
)

logger = logging.getLogger("analytics")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPORT_HTML_PATH = BASE_DIR / "analytics_report.html"


def compute_pipeline_metrics() -> Dict[str, Any]:
    """Computes all summary statistics and breakdown data from CSV databases."""
    init_database_files()

    df_rec = pd.read_csv(RECRUITERS_CSV)
    df_hist = pd.read_csv(EMAIL_SENT_HISTORY_CSV)

    total_scraped = len(df_rec)
    pending_leads = len(df_rec[df_rec["email_sent_status"] == "pending"])
    mismatched_leads = len(df_rec[df_rec["email_sent_status"] == "mismatched_role"])

    total_outreach = len(df_hist)
    sent_outreach = len(df_hist[df_hist["email_sent_status"] == "sent"])
    failed_outreach = len(df_hist[df_hist["email_sent_status"] == "failed"])

    # Follow-ups
    if not df_hist.empty and "followup_count" in df_hist.columns:
        followup_count = int(pd.to_numeric(df_hist["followup_count"], errors="coerce").fillna(0).sum())
    else:
        followup_count = 0

    # Replies
    if not df_hist.empty and "replied" in df_hist.columns:
        total_replies = int(pd.to_numeric(df_hist["replied"], errors="coerce").fillna(0).sum())
    else:
        total_replies = 0

    reply_rate = (total_replies / sent_outreach * 100) if sent_outreach > 0 else 0.0

    # Candidate Breakdown
    candidate_stats = []
    for c_key, c_info in CLIENTS.items():
        c_name = c_info.get("name", c_key)
        c_role = CANDIDATE_ROLES.get(c_key, {}).get("primary_role", "Software Engineer")
        
        if not df_hist.empty and "candidate" in df_hist.columns:
            c_df = df_hist[df_hist["candidate"].astype(str).str.lower() == c_key.lower()]
        else:
            c_df = pd.DataFrame(columns=EMAIL_SENT_HISTORY_SCHEMA)

        c_sent = len(c_df[c_df["email_sent_status"] == "sent"]) if "email_sent_status" in c_df.columns else 0
        c_replies = int(pd.to_numeric(c_df["replied"], errors="coerce").fillna(0).sum()) if "replied" in c_df.columns else 0
        c_followups = int(pd.to_numeric(c_df["followup_count"], errors="coerce").fillna(0).sum()) if "followup_count" in c_df.columns else 0
        c_rate = (c_replies / c_sent * 100) if c_sent > 0 else 0.0

        candidate_stats.append({
            "key": c_key,
            "name": c_name,
            "role": c_role,
            "sent": c_sent,
            "replies": c_replies,
            "followups": c_followups,
            "reply_rate": round(c_rate, 1)
        })

    # Recent Activity Records (last 15)
    recent_activity = []
    if not df_hist.empty:
        df_sorted = df_hist.sort_values(by="timestamp", ascending=False).head(15)
        for _, row in df_sorted.iterrows():
            recent_activity.append({
                "recruiter_name": str(row.get("recruiter_name", "Recruiter")),
                "recruiter_email": str(row.get("recruiter_email", "")),
                "role": str(row.get("role", "")),
                "candidate": str(row.get("candidate", "")).capitalize(),
                "timestamp": str(row.get("timestamp", "")),
                "status": str(row.get("email_sent_status", "sent")),
                "replied": int(row.get("replied", 0)) == 1,
                "followup_count": int(row.get("followup_count", 0))
            })

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scraped": total_scraped,
        "pending_leads": pending_leads,
        "mismatched_leads": mismatched_leads,
        "total_outreach": total_outreach,
        "sent_outreach": sent_outreach,
        "failed_outreach": failed_outreach,
        "followup_count": followup_count,
        "total_replies": total_replies,
        "reply_rate": round(reply_rate, 1),
        "candidates": candidate_stats,
        "recent_activity": recent_activity
    }


def generate_html_report(output_path: Path = REPORT_HTML_PATH) -> Path:
    """
    Renders the state-of-the-art dark-themed HTML analytics dashboard
    with Chart.js charts, glowing glassmorphic metric cards, and responsive tables.
    """
    metrics = compute_pipeline_metrics()

    cand_names = [c["name"] for c in metrics["candidates"]]
    cand_sent = [c["sent"] for c in metrics["candidates"]]
    cand_replies = [c["replies"] for c in metrics["candidates"]]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Recruitment & Outreach Automation Analytics</title>
  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <!-- Chart.js CDN -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg-dark: #0b0f19;
      --card-bg: rgba(23, 32, 54, 0.7);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent-indigo: #6366f1;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-rose: #f43f5e;
      --accent-amber: #f59e0b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: radial-gradient(circle at 10% 20%, #172033 0%, #0b0f19 90%);
      color: var(--text-main);
      min-height: 100vh;
      padding: 32px 24px;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1320px;
      margin: 0 auto;
    }}

    /* Header */
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 32px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
    }}

    .header-title h1 {{
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #818cf8 100%);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .header-title p {{
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }}

    .badge-live {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 9999px;
    }}

    .badge-live::before {{
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.5; transform: scale(0.85); }}
    }}

    /* Metric Cards Grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }}

    .metric-card {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 22px;
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }}

    .metric-card:hover {{
      transform: translateY(-3px);
      border-color: rgba(99, 102, 241, 0.4);
      box-shadow: 0 12px 30px -10px rgba(99, 102, 241, 0.2);
    }}

    .metric-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--card-accent, #6366f1), transparent);
    }}

    .metric-label {{
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .metric-value {{
      font-size: 32px;
      font-weight: 800;
      margin: 10px 0 4px;
      letter-spacing: -1px;
    }}

    .metric-sub {{
      font-size: 12px;
      color: var(--text-muted);
    }}

    /* Charts Section */
    .charts-grid {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
      margin-bottom: 32px;
    }}

    @media (max-width: 992px) {{
      .charts-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .chart-card {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
    }}

    .chart-title {{
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    /* Table Section */
    .section-card {{
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 32px;
    }}

    .table-container {{
      width: 100%;
      overflow-x: auto;
      margin-top: 16px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }}

    th {{
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 12px 16px;
      border-bottom: 1px solid var(--card-border);
    }}

    td {{
      padding: 14px 16px;
      font-size: 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    .badge {{
      display: inline-block;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 600;
      border-radius: 6px;
      text-transform: uppercase;
    }}

    .badge-sent {{
      background: rgba(99, 102, 241, 0.2);
      color: #818cf8;
      border: 1px solid rgba(99, 102, 241, 0.3);
    }}

    .badge-replied {{
      background: rgba(16, 185, 129, 0.2);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }}

    .badge-pending {{
      background: rgba(245, 158, 11, 0.2);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.3);
    }}

    .footer {{
      text-align: center;
      color: var(--text-muted);
      font-size: 13px;
      margin-top: 40px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-title">
        <h1>Recruitment Outreach & Automation Pipeline</h1>
        <p>Real-time analytics for US C2C contract outreach, resume tailoring, and recruiter engagement</p>
      </div>
      <div>
        <span class="badge-live">Live Pipeline Active &bull; {metrics["generated_at"]}</span>
      </div>
    </header>

    <!-- Top Metric Cards -->
    <section class="metrics-grid">
      <div class="metric-card" style="--card-accent: #6366f1;">
        <div class="metric-label">Total Scraped Leads</div>
        <div class="metric-value">{metrics["total_scraped"]}</div>
        <div class="metric-sub">{metrics["pending_leads"]} awaiting outreach dispatch</div>
      </div>

      <div class="metric-card" style="--card-accent: #06b6d4;">
        <div class="metric-label">Outreach Dispatched</div>
        <div class="metric-value">{metrics["sent_outreach"]}</div>
        <div class="metric-sub">{metrics["followup_count"]} threaded follow-ups sent</div>
      </div>

      <div class="metric-card" style="--card-accent: #10b981;">
        <div class="metric-label">Recruiter Replies</div>
        <div class="metric-value">{metrics["total_replies"]}</div>
        <div class="metric-sub">Verified via IMAP Inbox Sync</div>
      </div>

      <div class="metric-card" style="--card-accent: #f59e0b;">
        <div class="metric-label">Conversion Reply Rate</div>
        <div class="metric-value">{metrics["reply_rate"]}%</div>
        <div class="metric-sub">Average across all candidate portfolios</div>
      </div>
    </section>

    <!-- Charts Row -->
    <section class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">
          <span>Candidate Outreach & Response Performance</span>
          <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">Sent vs Replies</span>
        </div>
        <canvas id="candidateBarChart" height="120"></canvas>
      </div>

      <div class="chart-card">
        <div class="chart-title">
          <span>Lead Status Distribution</span>
          <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">Pipeline Breakdown</span>
        </div>
        <canvas id="statusDoughnutChart" height="180"></canvas>
      </div>
    </section>

    <!-- Candidate Performance Table -->
    <section class="section-card">
      <div class="chart-title">
        <span>Registered Candidate Profiles & Outreach Telemetry</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Primary Target Role</th>
              <th>Emails Sent</th>
              <th>Follow-Ups</th>
              <th>Replies Detected</th>
              <th>Conversion Rate</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
"""

    for c in metrics["candidates"]:
        html_content += f"""
            <tr>
              <td style="font-weight: 600;">{c['name']}</td>
              <td style="color: var(--text-muted);">{c['role']}</td>
              <td>{c['sent']}</td>
              <td>{c['followups']}</td>
              <td style="color: #34d399; font-weight: 600;">{c['replies']}</td>
              <td><span style="font-weight: 700; color: #818cf8;">{c['reply_rate']}%</span></td>
              <td><span class="badge badge-sent">Active</span></td>
            </tr>
"""

    html_content += """
          </tbody>
        </table>
      </div>
    </section>

    <!-- Recent Activity Table -->
    <section class="section-card">
      <div class="chart-title">
        <span>Recent Outreach & Communication History</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Recruiter Name</th>
              <th>Email Address</th>
              <th>Target Role</th>
              <th>Candidate</th>
              <th>Timestamp</th>
              <th>Follow-Up</th>
              <th>Reply Status</th>
            </tr>
          </thead>
          <tbody>
"""

    if metrics["recent_activity"]:
        for act in metrics["recent_activity"]:
            badge_class = "badge-replied" if act["replied"] else "badge-sent"
            status_label = "Replied" if act["replied"] else "Sent (Awaiting)"
            followup_str = f"Yes ({act['followup_count']})" if act["followup_count"] > 0 else "None"
            html_content += f"""
            <tr>
              <td style="font-weight: 500;">{act['recruiter_name']}</td>
              <td style="color: var(--accent-cyan);">{act['recruiter_email']}</td>
              <td>{act['role']}</td>
              <td>{act['candidate']}</td>
              <td style="color: var(--text-muted); font-size: 13px;">{act['timestamp']}</td>
              <td>{followup_str}</td>
              <td><span class="badge {badge_class}">{status_label}</span></td>
            </tr>
"""
    else:
        html_content += """
            <tr>
              <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">
                No outreach activity logged yet. Run Option 3 or Option 8 in the console to dispatch outreach.
              </td>
            </tr>
"""

    doughnut_labels = ["Sent Outreach", "Pending Leads", "Replies Detected"]
    doughnut_data = [metrics["sent_outreach"], metrics["pending_leads"], metrics["total_replies"]]

    html_content += f"""
          </tbody>
        </table>
      </div>
    </section>

    <footer class="footer">
      <p>Automated C2C Recruitment & Outreach Pipeline &bull; Generated dynamically</p>
    </footer>
  </div>

  <script>
    // Candidate Bar Chart
    const barCtx = document.getElementById('candidateBarChart').getContext('2d');
    new Chart(barCtx, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(cand_names)},
        datasets: [
          {{
            label: 'Sent Emails',
            data: {json.dumps(cand_sent)},
            backgroundColor: 'rgba(99, 102, 241, 0.7)',
            borderColor: '#6366f1',
            borderWidth: 1,
            borderRadius: 6
          }},
          {{
            label: 'Replies Received',
            data: {json.dumps(cand_replies)},
            backgroundColor: 'rgba(16, 185, 129, 0.8)',
            borderColor: '#10b981',
            borderWidth: 1,
            borderRadius: 6
          }}
        ]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{
            labels: {{ color: '#94a3b8', font: {{ family: 'Inter' }} }}
          }}
        }},
        scales: {{
          x: {{
            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
            ticks: {{ color: '#94a3b8', font: {{ family: 'Inter' }} }}
          }},
          y: {{
            beginAtZero: true,
            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
            ticks: {{ color: '#94a3b8', font: {{ family: 'Inter' }}, precision: 0 }}
          }}
        }}
      }}
    }});

    // Status Doughnut Chart
    const pieCtx = document.getElementById('statusDoughnutChart').getContext('2d');
    new Chart(pieCtx, {{
      type: 'doughnut',
      data: {{
        labels: {json.dumps(doughnut_labels)},
        datasets: [{{
          data: {json.dumps(doughnut_data)},
          backgroundColor: [
            'rgba(99, 102, 241, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(16, 185, 129, 0.8)'
          ],
          borderColor: '#172033',
          borderWidth: 2
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{
            position: 'bottom',
            labels: {{ color: '#94a3b8', font: {{ family: 'Inter' }} }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>
"""

    output_path = Path(output_path).resolve()
    output_path.write_text(html_content, encoding="utf-8")
    logger.info(f"Generated premium dark-themed HTML dashboard at: {output_path}")
    return output_path


if __name__ == "__main__":
    report_file = generate_html_report()
    print(f"Report ready: {report_file}")
