# Support Agent - Python Implementation

Runnable support-agent example with safe-by-default behavior:
- risk triage before drafting
- no auto-send tool in allowlist
- citation and policy checks
- artifacts + audit trail
- explicit human approval flag

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional for low-risk draft flow
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_TIMEOUT_SECONDS="60"

# default ticket is high-risk (handoff path)
python main.py

# run low-risk drafting path
TICKET_ID=T-1002 python main.py
```

## What this example demonstrates

- Conservative triage (`billing_refund`, `security`, `legal`, `outage`)
- Manual handoff for high-risk tickets
- LLM draft only for non-high-risk tickets
- Draft validation:
  - no hard commitments
  - required citations for policy-like claims
- No write-side customer send action

## Project layout

```text
python/
  README.md
  main.py
  llm.py
  gateway.py
  policy.py
  tools.py
  requirements.txt
```

## Notes

- This example uses in-memory stores for tickets/artifacts/audit.
- Replace in-memory stores with real services in production.
- Human approval is modeled via `requires_human_approval=true` output.

## License

MIT

## Result schema

- status is technical run state: success, blocked, stopped.
- outcome is business result when status=success: handoff or draft_ready.
