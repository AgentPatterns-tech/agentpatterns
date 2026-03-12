# Task Decomposition Agent - Python Implementation

Runnable implementation of a Task Decomposition agent that plans first,
executes steps sequentially through a controlled gateway, and synthesizes a final answer.

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
https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent

## What's inside

- Explicit `Plan -> Execute -> Combine` workflow
- Strict plan validation (`kind`, step schema, allowed keys/tools)
- Tool gateway with allowlist, budgeting, and loop detection
- Separate budgets for plan steps, execution steps, tool calls, and time
- Final synthesis call after all plan steps are executed
- Trace and stop reasons for invalid plans and runtime failures

## Learn the pattern (Docs)

Background concepts used by this example:

- Task Decomposition Agent
  https://agentpatterns.tech/en/agent-patterns/task-decomposition-agent
- ReAct Agent
  https://agentpatterns.tech/en/agent-patterns/react-agent
- Routing Agent
  https://agentpatterns.tech/en/agent-patterns/routing-agent
- Orchestrator Agent
  https://agentpatterns.tech/en/agent-patterns/orchestrator-agent

## Project layout

```text
examples/
  agent-patterns/
    task-decomposition-agent/
      python/
        README.md
        main.py
        llm.py
        gateway.py
        tools.py
        requirements.txt
```

## Notes

- Code and README are English-only by design.
- The website provides multilingual explanations and theory.

## License

MIT
