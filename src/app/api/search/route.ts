import Anthropic from "@anthropic-ai/sdk";

const SYSTEM_PROMPT = `You search the web for job listings and return structured results as JSON.

SEARCH TARGET: Sales, revenue, partnerships, business development, and GTM leadership roles (Director level and above) at wealth management technology companies in the US.

IMPORTANT RULES:
- Search one query at a time. After each search, review results before searching again.
- Extract any job listings you find from the search result snippets — titles, companies, locations, URLs.
- Partial information is fine. Use "Not disclosed" for missing compensation, "Unknown" for missing dates.
- You MUST always return a JSON array at the end, even if you only find 1-2 roles. Never return an apology or explanation instead.
- Your final text output must be ONLY the JSON array. No prose before or after.

JSON FORMAT (return array of these objects):
[{"company":"string","stage":"string","title":"string","url":"string","location":"string","compensation":"string","datePosted":"string","source":"string","isNew":false}]`;

const BACKOFF_DELAYS = [2000, 4000, 8000, 16000];

function extractJSON(text: string): unknown[] {
  // 1. Try direct parse
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed;
  } catch {
    // continue
  }

  // 2. Strip markdown code fences
  const fenceMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
  if (fenceMatch) {
    try {
      const parsed = JSON.parse(fenceMatch[1]);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      // continue
    }
  }

  // 3. Find first [ ... last ] in text
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start !== -1 && end > start) {
    try {
      const parsed = JSON.parse(text.slice(start, end + 1));
      if (Array.isArray(parsed)) return parsed;
    } catch {
      // continue
    }
  }

  return [];
}

async function callWithRetry(client: Anthropic, today: string) {
  let lastError: unknown;

  for (let attempt = 0; attempt <= BACKOFF_DELAYS.length; attempt++) {
    try {
      return await client.messages.create({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 16000,
        system: SYSTEM_PROMPT,
        tools: [
          {
            type: "web_search_20250305",
            name: "web_search",
            max_uses: 5,
          },
        ],
        messages: [
          {
            role: "user",
            content: `Today is ${today}. Search for these one at a time:
1. site:greenhouse.io OR site:lever.co "VP Sales" OR "Head of Sales" wealth management
2. site:linkedin.com/jobs "Director" OR "VP" wealthtech sales partnerships
3. Addepar OR Orion OR Envestnet OR iCapital OR CAIS careers sales director VP
4. "Head of Business Development" OR "CRO" fintech wealth management hiring 2025
5. Altruist OR Pontera OR Betterment OR Wealthfront open roles sales partnerships director

For each search, extract any matching job listings from the results. Then output ONLY a JSON array of all findings.`,
          },
        ],
      });
    } catch (error: unknown) {
      lastError = error;
      const isRateLimit =
        error instanceof Error && error.message.includes("rate_limit");
      if (isRateLimit && attempt < BACKOFF_DELAYS.length) {
        await new Promise((r) => setTimeout(r, BACKOFF_DELAYS[attempt]));
        continue;
      }
      throw error;
    }
  }
  throw lastError;
}

export const maxDuration = 120;

export async function POST() {
  const client = new Anthropic();
  const today = new Date().toISOString().split("T")[0];

  try {
    const response = await callWithRetry(client, today);

    // Collect all text blocks
    let resultText = "";
    const blockTypes: string[] = [];
    for (const block of response.content) {
      blockTypes.push(block.type);
      if (block.type === "text") {
        resultText += block.text;
      }
    }

    const jobs = extractJSON(resultText);

    return Response.json({
      jobs,
      debug: {
        stopReason: response.stop_reason,
        blockTypes,
        textLength: resultText.length,
        rawPreview: resultText.slice(0, 500),
      },
    });
  } catch (error: unknown) {
    console.error("Search error:", error);
    const message =
      error instanceof Error ? error.message : "An unknown error occurred";
    const isRateLimit = message.includes("rate_limit");
    return Response.json(
      {
        error: isRateLimit
          ? "Rate limited by Anthropic API. Please wait a minute and try again."
          : message,
      },
      { status: isRateLimit ? 429 : 500 }
    );
  }
}
