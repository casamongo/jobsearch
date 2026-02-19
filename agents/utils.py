"""Shared utilities for all agents."""

import json
import os
import time
from datetime import datetime
from pathlib import Path

# Resolve paths relative to the repo root (one level up from agents/)
REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
DATA_DIR = REPO_ROOT / "data"
RESULTS_DIR = DATA_DIR / "results"

MODEL = "claude-sonnet-4-5-20250929"
MODEL_RESEARCH = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 16_000
BACKOFF_DELAYS = [2, 4, 8, 16]


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def read_prompt(filename: str) -> str:
    """Read a prompt file from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    return path.read_text()


def read_skill() -> str:
    """Read the shared skill file."""
    return read_prompt("skill.md")


def extract_json(text: str):
    """Extract JSON from Claude's response text. Returns parsed JSON or None."""
    # 1. Direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Strip markdown code fences
    import re
    fence_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Find first { or [ ... last } or ]
    for open_char, close_char in [('{', '}'), ('[', ']')]:
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except (json.JSONDecodeError, TypeError):
                pass

    return None


def save_results(agent_name: str, data, date: str = None):
    """Save agent results to data/results/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date = date or today()
    filename = f"{agent_name}_{date}.json"
    path = RESULTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Results saved to {path}")
    return path


def load_results(agent_name: str, date: str = None):
    """Load agent results from data/results/."""
    date = date or today()
    filename = f"{agent_name}_{date}.json"
    path = RESULTS_DIR / filename
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def call_with_retry(client, create_kwargs: dict, max_retries: int = 4):
    """Call client.messages.create with exponential backoff on rate limits."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**create_kwargs)
        except Exception as e:
            last_error = e
            is_rate_limit = "rate_limit" in str(e).lower() or "429" in str(e)
            if is_rate_limit and attempt < max_retries:
                delay = BACKOFF_DELAYS[attempt]
                print(f"  Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            raise
    raise last_error


def collect_text(response) -> str:
    """Collect all text blocks from a Claude response."""
    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
    return "\n".join(text_parts)
