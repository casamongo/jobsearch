#!/usr/bin/env python3
"""
Agent 3 — LinkedIn Job Search (Browser Automation)

Uses Playwright to search LinkedIn Jobs like a human browser:
  - Navigates to LinkedIn job search
  - Runs keyword queries with filters
  - Paginates through results
  - Extracts job listing details

Usage:
    python -m agents.agent3_linkedin_search
    python -m agents.agent3_linkedin_search --dry-run
    python -m agents.agent3_linkedin_search --headed     # visible browser
    python -m agents.agent3_linkedin_search --input data/results/agent1_2026-02-19.json
"""

import argparse
import json
import random
import re
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from agents.utils import (
    load_results,
    save_results,
    today,
)

# LinkedIn job search base URL
LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/search/"

# Search queries: (keywords, location)
BROAD_QUERIES = [
    ('"VP Sales" OR "Head of Sales" wealthtech fintech', "United States"),
    ('"Chief Revenue Officer" wealth management fintech', "United States"),
    ('"Head of Business Development" financial technology', "United States"),
    ('"VP GTM" OR "Head of GTM" fintech', "United States"),
    ('"Director Partnerships" OR "Head of Partnerships" wealthtech', "United States"),
    ('"VP Sales" "portfolio management" OR "investment platform"', "United States"),
    ('"Director" OR "VP" "alternative investments" sales partnerships', "United States"),
    ('"Head of Sales" retirement OR "401k" technology', "United States"),
    ('"VP Business Development" "asset management" technology', "United States"),
    ('"CRO" OR "Chief Revenue Officer" "investment management"', "United States"),
]

# Seniority keywords to filter relevant roles
SENIORITY_KEYWORDS = [
    "director", "senior director", "vp", "vice president", "svp",
    "head of", "chief", "cro", "coo", "managing director", "general manager",
]

# Function keywords to filter relevant roles
FUNCTION_KEYWORDS = [
    "sales", "revenue", "partnerships", "business development", "gtm",
    "go-to-market", "client", "relationship", "consulting", "advisory",
    "commercial", "growth", "channel", "strategic alliances", "enterprise",
]

# Exclude these
EXCLUDE_KEYWORDS = [
    "engineer", "developer", "product manager", "designer", "data scientist",
    "marketing manager", "content", "compliance", "legal", "hr ", "human resources",
    "accounting", "finance manager", "operations manager",
]

# Known fintech companies from skill.md watchlist (always considered relevant)
WATCHLIST_COMPANIES = [
    # WealthTech
    "Addepar", "Orion", "Envestnet", "Betterment", "Wealthfront",
    "Riskalyze", "Nitrogen", "Advyzon", "Pontera", "Farther", "Vanilla",
    "Savvy Wealth", "LifeYield", "Conquest Planning", "Jump", "InvestCloud",
    "Altruist", "RightCapital", "Dynasty Financial", "Hightower",
    # InvestmentTech
    "iCapital", "CAIS", "YieldStreet", "Carta", "Forge Global", "Republic",
    "Moonfare", "AngelList", "Vise", "Tegus", "AlphaSense",
    # Asset Management Tech
    "SEI", "Morningstar", "BlackRock", "FactSet", "MSCI",
    "Clearwater Analytics", "Enfusion", "Arcesium",
    # PFM / Retirement Tech
    "Pershing", "BNY", "Empower", "Guideline", "Human Interest",
    "Vestwell", "Capitalize", "Magnifi",
    # Adjacent / Data / Regtech
    "Broadridge", "FIS", "SS&C", "ComplySci", "RIA in a Box", "Aumni",
]

# Industry-relevance keywords — at least one must appear in company name or job context
# to keep a role from a broad (non-company-targeted) search
INDUSTRY_KEYWORDS = [
    # Core fintech / wealth / investment terms
    "fintech", "wealthtech", "wealth", "invest", "capital", "asset",
    "financial", "finance", "advisory", "advisor", "fiduciary",
    "portfolio", "fund", "trading", "brokerage", "broker",
    "banking", "bank", "insurance", "mortgage", "lending",
    "retirement", "401k", "pension", "annuit",
    "robo-advis", "neobank",
    # Tech platforms serving finance
    "clearwater", "envestnet", "orion", "addepar", "morningstar",
    "factset", "msci", "sei ", "betterment", "wealthfront",
    "icapital", "cais", "carta", "vestwell", "altruist",
    "pontera", "riskalyze", "nitrogen", "broadridge",
    "pershing", "schwab", "fidelity", "vanguard",
    # Broader but still relevant
    "regtech", "compliance", "risk", "analytics",
    "saas" , "platform",
]

# Known non-fintech company name patterns to always exclude
NON_FINTECH_INDICATORS = [
    "pet", "hotel", "restaurant", "food", "pharma", "therapeutic",
    "healthcare", "medical", "biotech", "roofing", "solar",
    "construction", "hvac", "plumbing", "trucking", "freight",
    "logistics", "shipping", "warehouse", "retail", "fashion",
    "apparel", "clothing", "cosmetic", "beauty", "jewelry",
    "furniture", "real estate", "property group", "staffing",
    "recruiting", "recruitment", "headhunt", "talent search",
    "executive search", "sports", "athletic", "academy",
    "entertainment", "media group", "broadcast", "radio",
    "television", "studio", "hospitality", "resort",
    "automotive", "motor", "car dealer", "aerospace",
    "defense", "military", "government", "municipal",
    "church", "ministry", "nonprofit", "ngo",
]

DELAY_MIN = 2.0
DELAY_MAX = 5.0


def is_fintech_relevant(company: str, known_companies: set) -> bool:
    """Check if a company is likely in the fintech/wealth/investment space."""
    name_lower = company.strip().lower()

    if not name_lower or name_lower in ("confidential", "undisclosed", "stealth startup", "a hiring company"):
        return False

    # Known fintech company from Agent 1 → always include
    if name_lower in known_companies:
        return True

    # Obvious non-fintech → exclude
    if any(kw in name_lower for kw in NON_FINTECH_INDICATORS):
        return False

    # Has fintech/wealth/investment signal → include
    if any(kw in name_lower for kw in INDUSTRY_KEYWORDS):
        return True

    # No signal either way — exclude (conservative approach for broad searches)
    return False


def human_delay(min_s=DELAY_MIN, max_s=DELAY_MAX):
    """Random delay to mimic human behavior."""
    time.sleep(random.uniform(min_s, max_s))


def matches_criteria(title: str) -> bool:
    """Check if a job title matches GTM leadership criteria."""
    title_lower = title.lower()

    # Must have seniority indicator
    has_seniority = any(kw in title_lower for kw in SENIORITY_KEYWORDS)
    if not has_seniority:
        return False

    # Must have function indicator
    has_function = any(kw in title_lower for kw in FUNCTION_KEYWORDS)
    if not has_function:
        return False

    # Must not be excluded
    is_excluded = any(kw in title_lower for kw in EXCLUDE_KEYWORDS)
    if is_excluded:
        return False

    return True


def extract_jobs_from_page(page) -> list:
    """Extract job listings from the current LinkedIn search results page."""
    jobs = []

    # Wait for job cards to load
    try:
        page.wait_for_selector(".base-card, .job-search-card, .base-search-card", timeout=10000)
    except PlaywrightTimeout:
        return jobs

    # LinkedIn public job search uses base-card elements
    cards = page.query_selector_all(".base-card, .job-search-card, .base-search-card")

    for card in cards:
        try:
            # Extract title
            title_el = card.query_selector(".base-search-card__title, .base-card__full-link, h3")
            title = title_el.inner_text().strip() if title_el else ""

            if not title:
                continue

            # Extract company
            company_el = card.query_selector(".base-search-card__subtitle, h4, .base-card__subtitle")
            company = company_el.inner_text().strip() if company_el else ""

            # Extract location
            location_el = card.query_selector(".job-search-card__location, .base-search-card__metadata span")
            location = location_el.inner_text().strip() if location_el else ""

            # Extract URL
            link_el = card.query_selector("a[href*='/jobs/view/'], a.base-card__full-link")
            url = link_el.get_attribute("href") if link_el else ""
            if url:
                url = url.split("?")[0]  # Clean tracking params

            # Extract date
            date_el = card.query_selector("time, .base-search-card__listdate, .job-search-card__listdate")
            date_posted = ""
            if date_el:
                date_posted = date_el.get_attribute("datetime") or date_el.inner_text().strip()

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "datePosted": date_posted,
            })
        except Exception:
            continue

    return jobs


def scroll_to_load_all(page, max_scrolls=5):
    """Scroll down to load more job listings (lazy loading)."""
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        human_delay(1.0, 2.0)

        # Check for "See more jobs" button
        see_more = page.query_selector("button.infinite-scroller__show-more-button, button[aria-label*='more jobs']")
        if see_more:
            try:
                see_more.click()
                human_delay(1.5, 3.0)
            except Exception:
                break


def search_linkedin(page, keywords: str, location: str = "United States") -> list:
    """Run a single LinkedIn job search and extract results."""
    params = f"?keywords={keywords}&location={location}&f_TPR=r604800"  # past week
    url = LINKEDIN_JOBS_URL + params

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except PlaywrightTimeout:
        print(f"    Timeout loading search page")
        return []
    except Exception as e:
        print(f"    Error loading page: {e}")
        return []

    human_delay(2.0, 4.0)

    # Scroll to load more results
    scroll_to_load_all(page, max_scrolls=3)

    # Extract all jobs from the page
    raw_jobs = extract_jobs_from_page(page)

    return raw_jobs


def run_company_search(page, company_name: str) -> list:
    """Search LinkedIn for GTM roles at a specific company."""
    keywords = f'"{company_name}" sales OR partnerships OR revenue OR "business development" director OR VP OR head'
    return search_linkedin(page, keywords)


def run(dry_run: bool = False, input_file: str = None, headed: bool = False) -> dict:
    """Run Agent 3 with Playwright browser automation."""
    print("=" * 60)
    print("AGENT 3 — LinkedIn Job Search (Browser Automation)")
    print(f"Date: {today()}")
    print("=" * 60)

    # Load Agent 1 results
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

    # Build set of known fintech companies for industry filtering
    known_companies = set()
    for c in companies:
        name = c.get("company", "").strip().lower()
        if name:
            known_companies.add(name)
    # Include the hardcoded watchlist from skill.md
    for name in WATCHLIST_COMPANIES:
        known_companies.add(name.strip().lower())
    print(f"Known fintech companies for filtering: {len(known_companies)}")

    if dry_run:
        print(f"[DRY RUN] Would run {len(BROAD_QUERIES)} broad searches via Playwright")
        high = [c for c in companies if c.get("priority") == "high"]
        print(f"[DRY RUN] Plus {len(high)} company-targeted searches")
        print(f"[DRY RUN] Browser mode: {'headed' if headed else 'headless'}")
        return {"roles": [], "queries_run": []}

    all_roles = []
    queries_log = []
    seen_urls = set()

    with sync_playwright() as p:
        # Try explicit path first (for environments with pre-installed Chromium)
        import os
        chromium_path = os.environ.get("CHROMIUM_PATH")
        if not chromium_path:
            # Check common pre-installed locations
            candidates = [
                "/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/usr/bin/google-chrome",
            ]
            for c in candidates:
                if os.path.exists(c):
                    chromium_path = c
                    break

        launch_opts = {"headless": not headed}
        if chromium_path:
            launch_opts["executable_path"] = chromium_path
            print(f"Using browser: {chromium_path}")

        browser = p.chromium.launch(**launch_opts)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # ── Broad keyword searches ──
        print(f"\nRunning {len(BROAD_QUERIES)} broad keyword searches...")
        for i, (keywords, location) in enumerate(BROAD_QUERIES, 1):
            print(f"  [{i}/{len(BROAD_QUERIES)}] {keywords[:60]}...")

            raw_jobs = search_linkedin(page, keywords, location)
            matching = [j for j in raw_jobs if matches_criteria(j["title"])]
            relevant = [j for j in matching if is_fintech_relevant(j["company"], known_companies)]

            queries_log.append({
                "query": keywords,
                "raw_results": len(raw_jobs),
                "matching_results": len(matching),
                "industry_relevant": len(relevant),
            })

            for job in relevant:
                if job["url"] and job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    all_roles.append({
                        "company": job["company"],
                        "stage": "Unknown",
                        "title": job["title"],
                        "url": job["url"],
                        "location": job["location"],
                        "compensation": "Not disclosed",
                        "datePosted": job["datePosted"],
                        "source": "LinkedIn",
                        "segment": "Unknown",
                    })

            skipped = len(matching) - len(relevant)
            print(f"    Found {len(raw_jobs)} total, {len(matching)} title match, {len(relevant)} industry relevant ({skipped} non-fintech skipped)")
            human_delay()

        # ── Company-targeted searches ──
        high_companies = [c for c in companies if c.get("priority") == "high"]
        if high_companies:
            print(f"\nRunning {len(high_companies)} company-targeted searches...")
            for i, company in enumerate(high_companies, 1):
                name = company.get("company", "")
                segment = company.get("segment", "Unknown")
                stage = company.get("stage", "Unknown")
                print(f"  [{i}/{len(high_companies)}] {name}...")

                raw_jobs = run_company_search(page, name)
                matching = [j for j in raw_jobs if matches_criteria(j["title"])]

                queries_log.append({
                    "query": f"Company: {name}",
                    "raw_results": len(raw_jobs),
                    "matching_results": len(matching),
                })

                for job in matching:
                    if job["url"] and job["url"] not in seen_urls:
                        seen_urls.add(job["url"])
                        all_roles.append({
                            "company": job["company"] or name,
                            "stage": stage,
                            "title": job["title"],
                            "url": job["url"],
                            "location": job["location"],
                            "compensation": "Not disclosed",
                            "datePosted": job["datePosted"],
                            "source": "LinkedIn",
                            "segment": segment,
                        })

                print(f"    Found {len(raw_jobs)} total, {len(matching)} matching criteria")
                human_delay()

        browser.close()

    # Enrich with company data from Agent 1
    company_lookup = {c["company"].lower(): c for c in companies}
    for role in all_roles:
        company_data = company_lookup.get(role["company"].lower())
        if company_data:
            if role["stage"] == "Unknown":
                role["stage"] = company_data.get("stage", "Unknown")
            if role["segment"] == "Unknown":
                role["segment"] = company_data.get("segment", "Unknown")

    result = {"roles": all_roles, "queries_run": queries_log}

    print(f"\nTotal unique roles found: {len(all_roles)}")
    print(f"Queries run: {len(queries_log)}")

    # Summarize by source
    sources = {}
    for r in all_roles:
        s = r.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    for s, count in sorted(sources.items()):
        print(f"  {s}: {count} roles")

    save_results("agent3", result)

    return result


def main():
    parser = argparse.ArgumentParser(description="Agent 3 — LinkedIn Job Search (Browser Automation)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without running browser")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser window")
    parser.add_argument("--input", type=str, help="Path to Agent 1 results JSON file")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, input_file=args.input, headed=args.headed)

    roles = result.get("roles", [])
    if roles:
        print(f"\nTop roles found:")
        for i, r in enumerate(roles[:10], 1):
            print(f"  {i}. {r.get('company', '?')} — {r.get('title', '?')}")
            print(f"     {r.get('location', '?')} | {r.get('url', 'no url')}")


if __name__ == "__main__":
    main()
