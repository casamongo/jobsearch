#!/usr/bin/env python3
"""
Agent 1 — Company Research

Researches the fintech market to produce a ranked list of companies
likely hiring for GTM leadership roles. Uses web search to discover
companies beyond the known watchlist.

Usage:
    python -m agents.agent1_company_research
    python -m agents.agent1_company_research --dry-run
"""

import argparse
import json
import sys

import anthropic

from agents.utils import (
    MODEL_RESEARCH,
    MAX_TOKENS,
    call_with_retry,
    collect_text,
    extract_json,
    read_prompt,
    read_skill,
    save_results,
    today,
)


def build_system_prompt() -> str:
    skill = read_skill()
    agent_prompt = read_prompt("agent1-company-research-PROMPT.md")
    return f"""{agent_prompt}

---

## Skill Reference (Company Criteria, Watchlist, Segments)

{skill}"""


def build_user_message() -> str:
    return f"""Today is {today()}.

Research the fintech market (wealth tech, investment tech, asset management tech, personal financial management tech) and produce a ranked list of companies likely hiring for GTM leadership roles right now.

Start with the Known Companies Watchlist in the skill reference, then search for additional companies with strong hiring signals. Aim for 30+ companies total.

Return ONLY the JSON array as specified in the output format. No other text."""


def run(dry_run: bool = False) -> list:
    """Run Agent 1 and return the company list."""
    print("=" * 60)
    print("AGENT 1 — Company Research")
    print(f"Date: {today()}")
    print("=" * 60)

    if dry_run:
        print("[DRY RUN] Would call Claude with web search to research companies.")
        print("[DRY RUN] System prompt length:", len(build_system_prompt()), "chars")
        print("[DRY RUN] User message length:", len(build_user_message()), "chars")
        return []

    client = anthropic.Anthropic()

    print("Calling Claude with web search enabled...")
    print(f"Model: {MODEL_RESEARCH}")

    response = call_with_retry(client, {
        "model": MODEL_RESEARCH,
        "max_tokens": MAX_TOKENS,
        "system": build_system_prompt(),
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 10,
            }
        ],
        "messages": [
            {"role": "user", "content": build_user_message()}
        ],
    })

    print(f"Response received. Stop reason: {response.stop_reason}")
    print(f"Usage — input: {response.usage.input_tokens}, output: {response.usage.output_tokens}")

    text = collect_text(response)
    companies = extract_json(text)

    if companies is None:
        print("WARNING: Could not parse JSON from response.")
        print("Raw text preview:", text[:500])
        companies = []

    if isinstance(companies, dict):
        # If wrapped in an object, try to find the array
        for key in companies:
            if isinstance(companies[key], list):
                companies = companies[key]
                break

    if not isinstance(companies, list):
        print("WARNING: Parsed result is not a list.")
        companies = []

    print(f"\nFound {len(companies)} companies")

    # Summarize by priority
    priorities = {}
    for c in companies:
        p = c.get("priority", "unknown")
        priorities[p] = priorities.get(p, 0) + 1
    for p, count in sorted(priorities.items()):
        print(f"  {p}: {count}")

    # Save results
    save_results("agent1", companies)

    return companies


def main():
    parser = argparse.ArgumentParser(description="Agent 1 — Company Research")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without calling the API")
    args = parser.parse_args()

    companies = run(dry_run=args.dry_run)

    if companies:
        print(f"\nTop 5 companies:")
        for i, c in enumerate(companies[:5], 1):
            print(f"  {i}. {c.get('company', '?')} ({c.get('segment', '?')}) — {c.get('priority', '?')} priority")
            if c.get('hiring_signals'):
                print(f"     Signals: {c['hiring_signals']}")


if __name__ == "__main__":
    main()
