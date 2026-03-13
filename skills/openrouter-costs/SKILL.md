---
name: openrouter-costs
description: Query OpenRouter API usage and costs by day, week, and month
triggers:
  - cost
  - costs
  - spending
  - openrouter usage
  - how much have we spent
  - llm cost
  - api cost
---

# OpenRouter Cost Monitoring

Query LLM API usage and costs from OpenRouter.

## Usage

```bash
python3 /data/skills/openrouter-costs/scripts/openrouter_costs.py summary
```

## Output Fields

| Field | Description |
|-------|-------------|
| `daily_usd` | Spend today |
| `weekly_usd` | Spend this week |
| `monthly_usd` | Spend this month |
| `total_usd` | All-time spend on this key |
| `byok_*` | BYOK (bring-your-own-key) usage (e.g. OpenAI embeddings) |
| `limit` | Spend limit if set (null = unlimited) |
| `limit_remaining` | Remaining budget if limit set |

## Example Response

```json
{
  "daily_usd": 0.027,
  "weekly_usd": 1.594,
  "monthly_usd": 1.594,
  "total_usd": 1.594,
  "byok_daily_usd": 0.0,
  "byok_weekly_usd": 0.37,
  "byok_monthly_usd": 0.37,
  "limit": null,
  "limit_remaining": null
}
```

## Investigation Patterns

**Check today's spend:**
```bash
python3 /data/skills/openrouter-costs/scripts/openrouter_costs.py summary
```

**When asked about costs/spending**, run summary and present daily/weekly/monthly in a readable format.
