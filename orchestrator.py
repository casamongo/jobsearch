#!/usr/bin/env python3
"""
Multi-Agent Job Search Orchestrator

Sequences the three agents, merges results, deduplicates, detects new roles,
and optionally sends email alerts via SendGrid.

Usage:
    python orchestrator.py                  # Full run
    python orchestrator.py --dry-run        # No API calls or email
    python orchestrator.py --agent1-only    # Just company research
    python orchestrator.py --skip-agent1    # Use existing Agent 1 results, run 2+3
    python orchestrator.py --no-email       # Run everything but skip email
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from agents.utils import DATA_DIR, RESULTS_DIR, save_results, load_results, today


def find_latest_results(agent_name: str):
    """Find and load the most recent results file for an agent."""
    pattern = f"{agent_name}_*.json"
    files = sorted(RESULTS_DIR.glob(pattern), reverse=True)
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        date_str = f.stem.replace(f"{agent_name}_", "")
        print(f"  Found {f.name} ({date_str})")
        return data, date_str
    return None, None


def load_seen_roles() -> dict:
    """Load the registry of previously seen roles."""
    path = DATA_DIR / "seen_roles.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_seen_roles(seen: dict):
    """Save the updated seen roles registry."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "seen_roles.json"
    with open(path, "w") as f:
        json.dump(seen, f, indent=2)
    print(f"Seen roles registry saved ({len(seen)} total roles)")


def make_role_key(role: dict) -> str:
    """Create a dedup key from company + title (normalized)."""
    company = role.get("company", "").strip().lower()
    title = role.get("title", "").strip().lower()
    return f"{company}|{title}"


def merge_and_dedup(agent2_roles: list, agent3_roles: list) -> list:
    """Merge roles from Agent 2 and Agent 3, deduplicating by company+title."""
    seen_keys = {}
    merged = []

    for role in agent2_roles + agent3_roles:
        key = make_role_key(role)
        if key in seen_keys:
            # Merge sources
            existing = merged[seen_keys[key]]
            existing_source = existing.get("source", "")
            new_source = role.get("source", "")
            if new_source and new_source not in existing_source:
                existing["source"] = f"{existing_source}, {new_source}"
            # Prefer non-empty fields
            for field in ["url", "compensation", "datePosted", "location"]:
                if not existing.get(field) or existing[field] in ("Not disclosed", "Unknown", ""):
                    if role.get(field) and role[field] not in ("Not disclosed", "Unknown", ""):
                        existing[field] = role[field]
        else:
            seen_keys[key] = len(merged)
            merged.append(role)

    return merged


def find_new_roles(merged: list, seen: dict) -> tuple[list, list]:
    """Split merged roles into new and previously seen."""
    new_roles = []
    existing_roles = []

    for role in merged:
        key = make_role_key(role)
        if key in seen:
            existing_roles.append(role)
        else:
            role["isNew"] = True
            new_roles.append(role)

    return new_roles, existing_roles


def update_tracker(new_roles: list, date: str):
    """Append new roles to the markdown tracker."""
    tracker_path = DATA_DIR / "tracker.md"

    if not tracker_path.exists():
        with open(tracker_path, "w") as f:
            f.write("# Job Search Tracker\n\n")
            f.write("| # | Company | Stage | Title | Location | Comp | Date Posted | Source | Segment | Found |\n")
            f.write("|---|---------|-------|-------|----------|------|-------------|--------|---------|-------|\n")

    with open(tracker_path, "a") as f:
        f.write(f"\n## {date} — {len(new_roles)} new roles\n\n")
        for i, role in enumerate(new_roles, 1):
            title = role.get("title", "?")
            url = role.get("url", "")
            title_cell = f"[{title}]({url})" if url else title
            f.write(
                f"| {i} "
                f"| {role.get('company', '?')} "
                f"| {role.get('stage', '?')} "
                f"| {title_cell} "
                f"| {role.get('location', '?')} "
                f"| {role.get('compensation', 'Not disclosed')} "
                f"| {role.get('datePosted', '?')} "
                f"| {role.get('source', '?')} "
                f"| {role.get('segment', '?')} "
                f"| {date} |\n"
            )

    print(f"Tracker updated: {len(new_roles)} new roles appended")


def send_email(new_roles: list, date: str):
    """Send email alert via SendGrid with new role findings."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    to_email = os.environ.get("SENDGRID_TO_EMAIL")

    if not all([api_key, from_email, to_email]):
        print("SendGrid not configured (missing SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, or SENDGRID_TO_EMAIL)")
        print("Skipping email.")
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    # Build HTML email body
    rows = ""
    for role in new_roles:
        title = role.get("title", "?")
        url = role.get("url", "")
        title_html = f'<a href="{url}">{title}</a>' if url else title
        rows += f"""<tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('company', '?')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('stage', '?')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{title_html}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('location', '?')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('compensation', 'N/A')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('source', '?')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{role.get('segment', '?')}</td>
        </tr>"""

    html = f"""
    <h2>Job Search Alert — {date}</h2>
    <p><strong>{len(new_roles)} new GTM leadership roles found</strong></p>
    <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
        <thead>
            <tr style="background: #f5f5f5;">
                <th style="padding: 8px; text-align: left;">Company</th>
                <th style="padding: 8px; text-align: left;">Stage</th>
                <th style="padding: 8px; text-align: left;">Title</th>
                <th style="padding: 8px; text-align: left;">Location</th>
                <th style="padding: 8px; text-align: left;">Comp</th>
                <th style="padding: 8px; text-align: left;">Source</th>
                <th style="padding: 8px; text-align: left;">Segment</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    """

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=f"Job Search: {len(new_roles)} new GTM leadership roles — {date}",
        html_content=html,
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Email sent! Status: {response.status_code}")
    except Exception as e:
        print(f"Email failed: {e}")


def run_orchestrator(
    dry_run: bool = False,
    agent1_only: bool = False,
    skip_agent1: bool = False,
    no_email: bool = False,
    merge_only: bool = False,
):
    date = today()
    print("=" * 60)
    print("MULTI-AGENT JOB SEARCH ORCHESTRATOR")
    print(f"Date: {date}")
    print(f"Options: dry_run={dry_run}, agent1_only={agent1_only}, skip_agent1={skip_agent1}, no_email={no_email}, merge_only={merge_only}")
    print("=" * 60)

    from agents.utils import load_results

    if merge_only:
        # Load all existing results from disk — skip running any agents
        print("\nMerge-only mode. Loading existing results...")

        companies = load_results("agent1", date)
        if not companies:
            companies, _ = find_latest_results("agent1")
            companies = companies or []
        print(f"  Agent 1: {len(companies)} companies")

        agent2_result = load_results("agent2", date)
        if not agent2_result:
            agent2_result, _ = find_latest_results("agent2")
        agent2_result = agent2_result or {"roles": [], "coverage": []}

        agent3_result = load_results("agent3", date)
        if not agent3_result:
            agent3_result, _ = find_latest_results("agent3")
        agent3_result = agent3_result or {"roles": [], "queries_run": []}

        print(f"  Agent 2: {len(agent2_result.get('roles', []))} roles")
        print(f"  Agent 3: {len(agent3_result.get('roles', []))} roles")
    else:
        # ── Step 1: Agent 1 — Company Research ──
        from agents.agent1_company_research import run as run_agent1

        if skip_agent1:
            companies = load_results("agent1") or []
            print(f"\nSkipping Agent 1. Loaded {len(companies)} companies from existing results.")
        else:
            print("\n── Step 1: Agent 1 — Company Research ──")
            companies = run_agent1(dry_run=dry_run)

        if agent1_only:
            print("\n── Agent 1 only mode — stopping here ──")
            return

        # ── Step 2: Agents 2 & 3 in parallel ──
        from agents.agent2_career_pages import run as run_agent2
        from agents.agent3_linkedin_search import run as run_agent3

        print("\n── Step 2: Agents 2 & 3 (parallel) ──")

        agent2_result = {"roles": [], "coverage": []}
        agent3_result = {"roles": [], "queries_run": []}

        if dry_run:
            run_agent2(dry_run=True)
            run_agent3(dry_run=True)
        else:
            with ThreadPoolExecutor(max_workers=2) as executor:
                future2 = executor.submit(run_agent2, dry_run=False)
                future3 = executor.submit(run_agent3, dry_run=False)

                for future in as_completed([future2, future3]):
                    try:
                        result = future.result()
                        if future == future2:
                            agent2_result = result
                        else:
                            agent3_result = result
                    except Exception as e:
                        print(f"Agent error: {e}")

    # ── Step 3: Merge & Deduplicate ──
    print("\n── Step 3: Merge & Deduplicate ──")

    agent2_roles = agent2_result.get("roles", [])
    agent3_roles = agent3_result.get("roles", [])
    print(f"Agent 2 found: {len(agent2_roles)} roles")
    print(f"Agent 3 found: {len(agent3_roles)} roles")

    merged = merge_and_dedup(agent2_roles, agent3_roles)
    print(f"After dedup: {len(merged)} unique roles")

    # Check against seen roles
    seen = load_seen_roles()
    new_roles, existing_roles = find_new_roles(merged, seen)
    print(f"New roles: {len(new_roles)}")
    print(f"Previously seen: {len(existing_roles)}")

    # Update seen roles registry
    for role in new_roles:
        key = make_role_key(role)
        seen[key] = {
            "company": role.get("company"),
            "title": role.get("title"),
            "first_seen": date,
            "url": role.get("url"),
            "segment": role.get("segment"),
        }
    save_seen_roles(seen)

    # Update tracker
    if new_roles:
        update_tracker(new_roles, date)

    # Save summary
    summary = {
        "date": date,
        "companies_researched": len(companies),
        "agent2_roles": len(agent2_roles),
        "agent3_roles": len(agent3_roles),
        "merged_unique": len(merged),
        "new_roles": len(new_roles),
        "previously_seen": len(existing_roles),
        "total_seen_all_time": len(seen),
        "roles": new_roles,
    }
    save_results("summary", summary)

    # ── Step 4: Email ──
    if new_roles and not no_email and not dry_run:
        print("\n── Step 4: Email Alert ──")
        send_email(new_roles, date)
    elif not new_roles:
        print("\nNo new roles found — skipping email.")
    elif no_email:
        print("\n--no-email flag set — skipping email.")

    # ── Display matching roles ──
    if merged:
        print("\n" + "=" * 60)
        print("MATCHING ROLES")
        print("=" * 60)
        for i, role in enumerate(merged, 1):
            new_tag = " ✦ NEW" if role.get("isNew") else ""
            print(f"\n  {i}. {role.get('title', '?')}{new_tag}")
            print(f"     Company:  {role.get('company', '?')} ({role.get('stage', '?')})")
            print(f"     Location: {role.get('location', '?')}")
            print(f"     Comp:     {role.get('compensation', 'Not disclosed')}")
            print(f"     Source:   {role.get('source', '?')}")
            print(f"     Segment:  {role.get('segment', '?')}")
            url = role.get("url", "")
            if url:
                print(f"     Link:     {url}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("RUN COMPLETE")
    print(f"  Companies researched: {len(companies)}")
    print(f"  Roles from career pages (Agent 2): {len(agent2_roles)}")
    print(f"  Roles from LinkedIn/boards (Agent 3): {len(agent3_roles)}")
    print(f"  Unique roles after dedup: {len(merged)}")
    print(f"  NEW roles this run: {len(new_roles)}")
    print(f"  Total roles seen all time: {len(seen)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Job Search Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="No API calls or email")
    parser.add_argument("--agent1-only", action="store_true", help="Run only Agent 1 (company research)")
    parser.add_argument("--skip-agent1", action="store_true", help="Skip Agent 1, use existing results")
    parser.add_argument("--no-email", action="store_true", help="Run everything but skip email")
    parser.add_argument("--merge-only", action="store_true", help="Skip all agents, merge existing results only")
    args = parser.parse_args()

    run_orchestrator(
        dry_run=args.dry_run,
        agent1_only=args.agent1_only,
        skip_agent1=args.skip_agent1,
        no_email=args.no_email,
        merge_only=args.merge_only,
    )


if __name__ == "__main__":
    main()
