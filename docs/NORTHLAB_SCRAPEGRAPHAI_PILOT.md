# NorthLab — ScrapeGraphAI local pilot

**Scope:** Manual enrichment of explicitly approved public company pages. This pilot is **not** a lead-finder, sales classifier, or production crawler. It does not touch Firestore, EKSİQ, Telegram, or the production NorthLab Radar.

## What it actually does

1. The operator supplies an HTTPS URL and its **exact** hostname as a manual allowlist.
2. The script checks the input against simple local-target filters and requires an explicit `--run` flag.
3. If run is enabled, the official `SmartScraperGraph` parses the page using the **locally installed Ollama Llama 3.2 model**, not the paid ScrapeGraphAI API.
4. It emits JSON with company description, public services and *possibly* relevant gaps, **always flagged for human review**. It never invents eligibility or automatic intent scores.

**Security limitation:** ScrapeGraphAI has an [open SSRF issue](https://github.com/ScrapeGraphAI/Scrapegraph-ai/issues/1115). Start-URL allowlisting alone does **not** protect against redirect-to-private-IP or DNS-rebinding attacks. Run this **only on an isolated operator workstation or network sandbox** with outbound access to private networks and cloud metadata endpoints blocked. Do not expose this script as a web endpoint or run it against untrusted URLs. Respect website terms, robots rules and rate limits; do not circumvent login, paywalls or anti-bot controls.

## Windows local setup (optional; only when operator is ready)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install scrapegraphai
python -m playwright install chromium
# Install Ollama separately from https://ollama.com/download and start it locally
ollama pull llama3.2
```

### Free dry-run — no model or web request

```powershell
python northlab_sga_pilot.py --url https://northlab.pro/ --allow-host northlab.pro
```

### Real extraction — one approved company page, local model required

```powershell
python northlab_sga_pilot.py --url https://northlab.pro/ --allow-host northlab.pro --run
```

`northlab.pro` here is only a safe **owned-site smoke-test example**, **not a NorthLab sales prospect**. Real company prospects require an independently collected, source-backed shortlist and permission-compliant use.

### Tests

```powershell
python -m unittest -v test_northlab_sga_pilot.py
```

## Acceptance gate

- Must run with no paid ScrapeGraphAI account/API key.
- A manual public-source example must produce structured output without false purchasing intent.
- Every finding must be checked against the original source with a real quotation and dated link; the script itself marks the evidence as unverified.
- No automatic candidate alert, CRM import, or contact research until separate validation and review.
- Record local CPU/RAM use, extraction runtime and failure rate before extending beyond one-page pilot.

**Current status (16 Nov 2026):** 11 local unit tests PASS, dry-run works. **Not yet tested with a live ScrapeGraphAI/Ollama installation.** No evidence of leads generated.
