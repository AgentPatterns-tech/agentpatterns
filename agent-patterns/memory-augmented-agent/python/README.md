# Memory-Augmented Agent - Python Implementation

Runnable implementation of a memory-augmented agent flow where the system
captures durable user facts, stores them with policy checks, retrieves relevant
memory in a later session, and applies memory to final response generation.

---

## Quick start

```bash
# (optional) create venv
python -m venv .venv && source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# set API key
export OPENAI_API_KEY="sk-..."

# run the agent
python main.py
```

## Full walkthrough

Read the complete implementation guide:
https://agentpatterns.tech/en/agent-patterns/memory-augmented-agent

## What's inside

- Capture -> Store -> Retrieve -> Apply flow
- Memory write validation (`key/value/scope/ttl/confidence`)
- Policy allowlist vs execution allowlist for memory keys and scopes
- TTL-based memory lifecycle and bounded in-memory store
- Strict policy boundary: unknown memory `key`/`scope` stops the run
- Grounded final answer with memory-key allowlist check
- `resolved_scopes` in history (execution-gated scopes actually used at runtime)
- Trace and history for auditability

## Project layout

```text
examples/
  agent-patterns/
    memory-augmented-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        memory_store.py
        requirements.txt
```

## Notes

- This example is English-only in code; narrative is localized on the website.
- This demo simulates two sessions within one process run (in-memory store).
- For real cross-session persistence, use an external store (Postgres/Redis/Vector DB).
- The website provides multilingual explanations and theory.

## License

MIT
