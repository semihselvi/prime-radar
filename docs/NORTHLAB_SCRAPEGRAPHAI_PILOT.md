# NorthLab — ScrapeGraphAI + Cloudflare Workers AI on GitHub (pilot)

**No Windows, no Ollama, no new hosting.** GitHub Actions runs Python. Cloudflare Workers AI supplies an OpenAI-compatible model API. This is a single-page, manually approved experiment, **not** a production lead radar.

## What is ready
- Code and mocked API/offline tests; dry-run has **zero network/model calls**.
- On `--run`, uses only the hardcoded owned `https://northlab.pro/` URL. Redirects rejected and HTML response capped at 180 KB.
- Extracts visible page text before passing it to ScrapeGraphAI. The library receives **local text**, never a remote URL, avoiding its known SSRF FetchNode path.
- ScrapeGraphAI calls Cloudflare's OpenAI-compatible endpoint with free-tier-eligible `@cf/zai-org/glm-4.7-flash`. No SGA managed API.
- Results marked `review_required` with `qualified_sales_lead=false`. Invented supporting quotes are removed; other fields still require human verification.
- No Firestore, EKSİQ, Telegram, CRM write, automated outreach or recurring schedule.

## One-time setup for a real model test
1. Cloudflare dashboard > Workers AI > Use REST API. Create a scoped Workers AI token (official guide recommends the Workers AI API Token template).
2. In GitHub `semihselvi/prime-radar` > Settings > Secrets and variables > Actions, configure **repository secrets**:
   - `CLOUDFLARE_ACCOUNT_ID`: 32-digit hex account ID
   - `CLOUDFLARE_API_TOKEN`: scoped Workers AI token
3. After PR review and merge to `main`, GitHub > Actions > **NORTHLAB - ScrapeGraphAI Pilot CI** > Run workflow > set **run_live=true**. Default is **false**, so no accidental AI bill/usage.
4. Confirm one `review_required` JSON artifact exists. If unavailable, the job must fail without guessing the answer. Do not publish raw company text or token.

## Scope and limitations
Cloudflare Workers Free has **10,000 Neurons/day**, shared by all Workers AI usage; daily usage is **not** guaranteed. On Workers Paid, usage beyond the free allocation can be charged. Pilot uses one model inference and must be opt-in. No live call was possible during PR authoring without configured account token.

The selected model is an example free-tier-eligible Cloudflare model, not a universal compatibility guarantee. ScrapeGraphAI's OpenAI custom base URL path requires a real integration run to validate. The workflow installs ScrapeGraphAI only for an explicit live test.

**Security:** [ScrapeGraphAI SSRF issue #1115](https://github.com/ScrapeGraphAI/Scrapegraph-ai/issues/1115) remains relevant for any direct URL scraping. Never pass public or user-supplied URLs to its FetchNode. For more firms, first design a safe fetcher that enforces public-IP address connections across redirects and DNS changes, plus robots/rate limits and source-specific permission checks. The pilot's hardcoded owned domain must not be generalized by changing a CLI flag.

**Commercial gate:** This is an extraction proof only. A successful JSON response is **not** a customer lead. Additional company discovery, contact channel validation, buyer signal and dedup are required before any sales outreach.
