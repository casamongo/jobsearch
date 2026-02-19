#!/usr/bin/env python3
"""
Agent 2 — Career Page Search

Takes a company list from Agent 1 and visits each company's career page
(Greenhouse, Lever, Workday, direct) to find GTM leadership openings.

Usage:
    python -m agents.agent2_career_pages
    python -m agents.agent2_career_pages --dry-run
    python -m agents.agent2_career_pages --input data/results/agent1_2026-02-19.json
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
    agent_prompt = read_prompt("agent2-career-pages-PROMPT.md")
    return f"""{agent_prompt}

---

## Skill Reference (Role Criteria, Segments)

{skill}"""


def build_user_message(companies: list) -> str:
    # Filter to high and medium priority, limit to top 25 for search budget
    prioritized = [c for c in companies if c.get("priority") in ("high", "medium")]
    if not prioritized:
        prioritized = companies
    prioritized = prioritized[:25]

    companies_json = json.dumps(prioritized, indent=2)

    return f"""Today is {today()}.

Here are the companies to search (from Agent 1's research). Focus on high and medium priority companies:

{companies_json}

For each company, visit their career page URL and check for GTM leadership roles (Director+) in sales, revenue, partnerships, business development, GTM, and client management.

Also try common ATS platforms:
- jobs.lever.co/{{company}}
- boards.greenhouse.io/{{company}}

Return the JSON output as specified in the output format. Include both the roles found and the coverage log."""


def run(dry_run: bool = False, input_file: str = None) -> dict:
    """Run Agent 2 and return roles + coverage."""
    print("=" * 60)
    print("AGENT 2 — Career Page Search")
    print(f"Date: {today()}")
    print("=" * 60)

    # Load Agent 1 results
    if input_file:
        with open(input_file) as f:
            companies = json.load(f)
        print(f"Loaded {len(companies)} companies from {input_file}")
    else:
        companies = load_results("agent1")
        if companies is None:
            print("ERROR: No Agent 1 results found for today. Run Agent 1 first, or pass --input.")
            return {"roles": [], "coverage": []}
        print(f"Loaded {len(companies)} companies from today's Agent 1 results")

    if dry_run:
        print(f"[DRY RUN] Would search career pages for {len(companies)} companies.")
        high = sum(1 for c in companies if c.get("priority") == "high")
        medium = sum(1 for c in companies if c.get("priority") == "medium")
        print(f"[DRY RUN] High priority: {high}, Medium: {medium}")
        return {"roles": [], "coverage": []}

    client = anthropic.Anthropic()

    print("Calling Claude with web search to check career pages...")
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
        result = {"roles": [], "coverage": []}

    if isinstance(result, list):
        # Agent returned just a roles array
        result = {"roles": result, "coverage": []}

    roles = result.get("roles", [])
    coverage = result.get("coverage", [])

    print(f"\nFound {len(roles)} matching roles")
    print(f"Coverage: {len(coverage)} companies checked")

    checked = sum(1 for c in coverage if c.get("status") == "checked")
    print(f"  Successfully checked: {checked}")

    # Save results
    save_results("agent2", result)

    return result


def main():
    parser = argparse.ArgumentParser(description="Agent 2 — Career Page Search")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without calling the API")
    parser.add_argument("--input", type=str, help="Path to Agent 1 results JSON file (default: today's results)")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, input_file=args.input)

    roles = result.get("roles", [])
    if roles:
        print(f"\nTop roles found:")
        for i, r in enumerate(roles[:10], 1):
            print(f"  {i}. {r.get('company', '?')} — {r.get('title', '?')}")
            print(f"     {r.get('location', '?')} | {r.get('source', '?')} | {r.get('url', 'no url')}")


if __name__ == "__main__":
    main()
