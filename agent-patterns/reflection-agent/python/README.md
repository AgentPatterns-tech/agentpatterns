# Reflection Agent - Python Implementation

Runnable implementation of a Reflection agent with one controlled review pass,
one optional patch-only revision, and strict stop reasons for auditability.

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
https://agentpatterns.tech/en/agent-patterns/reflection-agent

## What's inside

- `Draft -> Review -> Revise -> Finalize` flow
- Reflection review contract (`approve | revise | escalate`)
- Policy vs execution split for reflection decisions
- Patch guardrails (`no_new_facts`, max edit distance, one revision)
- Run budgets (`max_seconds`, length limits)
- Structured `trace` and `history`

## Project layout

```text
examples/
  agent-patterns/
    reflection-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        context.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- This demo keeps one in-memory run and does not include persistent storage.

## License

MIT
