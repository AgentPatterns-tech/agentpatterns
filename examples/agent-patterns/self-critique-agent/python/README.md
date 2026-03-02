# Self-Critique Agent - Python Implementation

Runnable implementation of a Self-Critique agent with one critique pass, one
constrained revision, and explicit audit logging for production monitoring.

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
https://agentpatterns.tech/en/agent-patterns/self-critique-agent

## What's inside

- `Draft -> Critique -> Revise -> Audit` flow
- Structured critique contract (`severity`, `risks`, `required_changes`)
- Policy vs execution split for critique decisions
- Constrained revision checks (`no_new_facts`, length increase cap)
- Audit diff metadata for observability
- Trace and history for run-level debugging

## Project layout

```text
examples/
  agent-patterns/
    self-critique-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        context.py
        audit.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- This demo keeps all state in one process run.
- If `policy_hints.avoid_absolute_guarantees=true`, restricted claims such as
  `resolved`/`incident closed` are blocked even if they appeared in draft.

## License

MIT
