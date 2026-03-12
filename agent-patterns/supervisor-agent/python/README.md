# Supervisor Agent - Python Implementation

Runnable implementation of a supervisor-controlled support flow where a worker
proposes actions, a supervisor enforces policy, and only approved actions execute.

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
https://agentpatterns.tech/en/agent-patterns/supervisor-agent

## What's inside

- Worker action loop (`tool` / `final`) with strict JSON action validation
- Supervisor policy decisions (`approve`, `revise`, `block`, `escalate`)
- Human-approval simulation for high-risk refunds
- Execution boundary with allowlist + budget + loop guards
- Trace and history for auditability

## Project layout

```text
examples/
  agent-patterns/
    supervisor-agent/
      python/
        README.md
        main.py
        llm.py
        supervisor.py
        gateway.py
        tools.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
