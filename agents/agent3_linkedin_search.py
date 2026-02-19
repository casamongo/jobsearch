#!/usr/bin/env python3
"""
Agent 3 — LinkedIn & Job Board Search

Runs keyword-based searches on LinkedIn and other job boards to find
GTM leadership roles. Uses both broad queries and company-targeted searches.

Usage:
    python -m agents.agent3_linkedin_search
    python -m agents.agent3_linkedin_search --dry-run
    python -m agents.agent3_linkedin_search --input data/results/agent1_2026-02-19.json
"""

import argparse
import json
import sys

import anthropic

from agents.utils import (
    MODEL,
    MAX_TOKENS,
    call_with_retry,
    collect_text,
    extract_json,
    load_results,
    read_prompt,
    read_skill,
    save_results,
    today,
)


def build_system_prompt() -> str:
    skill = read_skill()
    agent_prompt = read_prompt("agent3-linkedin-search-PROMPT.md")
    return f"""{agent_prompt}

---

## Skill Reference (Role Criteria, Company Criteria, Segments)

{skill}"""


def build_user_message(companies: list) -> str:
    # Pass top companies for company-targeted searches
    top_companies = [c for c in companies if c.get("priority") == "high"][:15]
    company_names = [c.get("company", "") for c in top_companies]

    return f"""Today is {today()}.

Run broad keyword searches on LinkedIn and job boards to find GTM leadership roles (Director+) at fintech companies focused on wealth management, investment tech, asset management tech, and personal financial management tech.

Top priority companies from Agent 1 research (use for company-targeted searches):
{json.dumps(company_names, indent=2)}

Run at least 10 broad keyword searches PLUS company-targeted searches for the top companies above.

Return the JSON output as specified in the output format. Include both the roles found and the queries_run log."""


def run(dry_run: bool = False, input_file: str = None) -> dict:
    """Run Agent 3 and return roles + query log."""
    print("=" * 60)
    print("AGENT 3 — LinkedIn & Job Board Search")
    print(f"Date: {today()}")
    print("=" * 60)

    # Load Agent 1 results (optional — Agent 3 can also run independently)
    companies = []
    if input_file:
        with open(input_file) as f:
            companies = json.load(f)
        print(f"Loaded {len(companies)} companies from {input_file}")
    else:
        companies = load_results("agent1") or []
        if companies:
            print(f"Loaded {len(companies)} companies from today's Agent 1 results")
        else:
            print("No Agent 1 results found — running with broad searches only")

    if dry_run:
        print(f"[DRY RUN] Would run 10+ keyword searches on LinkedIn/job boards.")
        if companies:
            high = sum(1 for c in companies if c.get("priority") == "high")
            print(f"[DRY RUN] Plus company-targeted searches for {high} high-priority companies.")
        return {"roles": [], "queries_run": []}

    client = anthropic.Anthropic()

    print("Calling Claude with web search for LinkedIn/job board queries...")
    print(f"Model: {MODEL}")

    response = call_with_retry(client, {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": build_system_prompt(),
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 20,
            }
        ],
        "messages": [
            {"role": "user", "content": build_user_message(companies)}
        ],
    })

    print(f"Response received. Stop reason: {response.stop_reason}")
    print(f"Usage — input: {response.usage.input_tokens}, output: {response.usage.output_tokens}")

    text = collect_text(response)
    result = extract_json(text)

    if result is None:
        print("WARNING: Could not parse JSON from response.")
        print("Raw text preview:", text[:500])
        result = {"roles": [], "queries_run": []}

    if isinstance(result, list):
        # Agent returned just a roles array
        result = {"roles": result, "queries_run": []}

    roles = result.get("roles", [])
    queries = result.get("queries_run", [])

    print(f"\nFound {len(roles)} matching roles")
    print(f"Queries run: {len(queries)}")

    # Summarize by source
    sources = {}
    for r in roles:
        s = r.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    for s, count in sorted(sources.items()):
        print(f"  {s}: {count} roles")

    # Save results
    save_results("agent3", result)

    return result


def main():
    parser = argparse.ArgumentParser(description="Agent 3 — LinkedIn & Job Board Search")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without calling the API")
    parser.add_argument("--input", type=str, help="Path to Agent 1 results JSON file (default: today's results)")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, input_file=args.input)

    roles = result.get("roles", [])
    if roles:
        print(f"\nTop roles found:")
        for i, r in enumerate(roles[:10], 1):
            print(f"  {i}. {r.get('company', '?')} — {r.get('title', '?')}")
            print(f"     {r.get('location', '?')} | {r.get('source', '?')}")


if __name__ == "__main__":
    main()
