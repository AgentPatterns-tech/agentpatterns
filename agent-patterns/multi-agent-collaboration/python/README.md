# Multi-Agent Collaboration - Python Implementation

Runnable implementation of a multi-agent collaboration flow where specialized
agents align on one launch decision across multiple rounds.

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
https://agentpatterns.tech/en/agent-patterns/multi-agent-collaboration

## What's inside

- Role-based team loop (`demand`, `finance`, `risk`)
- Shared context board passed to every role
- Collaboration gateway with strict contribution contract
- Round policy: conflict detection + consensus rule
- Runtime budgets (`max_rounds`, `max_messages`, `max_seconds`)
- Final synthesis after team alignment
- Trace and history for auditability

## Project layout

```text
examples/
  agent-patterns/
    multi-agent-collaboration/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        signals.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
