# Orchestrator Agent - Python Implementation

Runnable implementation of an orchestrator agent that plans sub-tasks,
runs workers in parallel, and composes one final operations answer.

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
https://agentpatterns.tech/en/agent-patterns/orchestrator-agent

## What's inside

- Plan step (`kind=plan`) with strict schema validation
- Separate policy and execution allowlists for workers
- Parallel dispatch with per-task timeout and retry-on-timeout
- Global runtime deadline enforced in gateway dispatch
- Critical vs non-critical task handling
- Final synthesis after aggregation
- Execution trace and stop reasons for debugging

## Project layout

```text
examples/
  agent-patterns/
    orchestrator-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        workers.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
