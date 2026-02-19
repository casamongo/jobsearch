import Anthropic from "@anthropic-ai/sdk";

const SYSTEM_PROMPT = `You are a job search agent. Find open GTM/commercial leadership roles at wealthtech companies in the US.

CRITERIA:
- Seniority: Director+ (Director, VP, SVP, Head of, C-suite)
- Functions: Sales, Revenue, Partnerships, Business Development, GTM Strategy, Client Management leadership, GM/P&L
- Exclude: Engineering, Product, Design, Marketing-only, Operations, Compliance, Legal, Finance, HR
- Companies: Wealthtech SaaS, digital wealth, advisor tech, robo-advisory, alt investment platforms, retirement tech, fintech with wealth vertical
- Prioritize private/growth-stage companies. Include public companies after.
- US-based roles (remote/hybrid/onsite). International only if US-remote eligible.
- Comp: $200K+ total. If not listed, note "Not disclosed"

WATCHLIST COMPANIES: Addepar, Orion, Envestnet, Betterment, Wealthfront, Nitrogen, Advyzon, Pontera, Farther, Vanilla, Savvy Wealth, LifeYield, InvestCloud, SEI, Morningstar, Dynasty Financial, Hightower, YieldStreet, CAIS, iCapital, Altruist, RightCapital

OUTPUT: Return ONLY a JSON array (no other text) with objects having these fields:
{"company":"string","stage":"string","title":"string","url":"string","location":"string","compensation":"string","datePosted":"string","source":"string","isNew":boolean}
isNew = true if posted within last 14 days. Find 10-15+ roles.`;

const BACKOFF_DELAYS = [2000, 4000, 8000, 16000];

async function callWithRetry(client: Anthropic, today: string) {
  let lastError: unknown;

  for (let attempt = 0; attempt <= BACKOFF_DELAYS.length; attempt++) {
    try {
      return await client.messages.create({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 4096,
        system: SYSTEM_PROMPT,
        tools: [
          {
            type: "web_search_20250305",
            name: "web_search",
            max_uses: 10,
          },
        ],
        messages: [
          {
            role: "user",
            content: `Today is ${today}. Search for current open wealthtech GTM and commercial leadership jobs. Use varied queries: "VP Sales" wealthtech, "Head of Partnerships" wealth management, "CRO" fintech wealth, "Director Business Development" advisor technology. Search LinkedIn, Lever, Greenhouse, Indeed, and company career pages. Return JSON array only.`,
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

    let resultText = "";
    for (const block of response.content) {
      if (block.type === "text") {
        resultText += block.text;
      }
    }

    let jobs = [];
    try {
      jobs = JSON.parse(resultText);
    } catch {
      const jsonMatch = resultText.match(/\[[\s\S]*\]/);
      if (jsonMatch) {
        jobs = JSON.parse(jsonMatch[0]);
      }
    }

    return Response.json({ jobs, raw: resultText });
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
